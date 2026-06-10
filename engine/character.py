from dataclasses import dataclass, field

from engine.events import Event
from engine.llm import LLMClient
from engine.stage import Stage


@dataclass
class Character:
    name: str
    persona: str
    goal: str
    voice: str
    directive: str = ""  # 导演钦定的首要目标(凌驾旧 goal);空=无钦定
    private_notes: list[str] = field(default_factory=list)
    oneshot_notes: list[str] = field(default_factory=list)  # 一次性叮嘱,演完即清空
    active: bool = True  # 退场(死亡/离开)后置 False,不再参与回合

    def system_prompt(self, director_will: str = "") -> str:
        parts = [
            f"你是「{self.name}」。",
            f"人设:{self.persona}",
        ]
        if director_will:
            parts.append(
                f"[导演当前走向——常驻最高优先,顺着它推进剧情,用你人设的方式而非生硬复述]:{director_will}"
            )
        if self.directive:
            parts.append(
                f"[当前首要目标(最高优先,凌驾旧目标;无论世界如何剧变都坚持,"
                f"并主动借眼前的新处境推进)]:{self.directive}"
            )
            parts.append(f"旧目标(次要,与首要目标不冲突时可保留):{self.goal}")
        else:
            parts.append(f"目标:{self.goal}")
        parts += [
            f"说话风格:{self.voice}",
            "你正在出演一部互动剧。始终保持角色,不要跳出,不要替别的角色说话。",
        ]
        notes = list(self.private_notes)
        notes += [f"{n}(仅限本回合,演完即止)" for n in self.oneshot_notes]
        if notes:
            parts.append(
                "\n[导演私下指令——最高优先级,你必须严格遵守下列每一条;"
                "即使与场上其他人不同、与你之前的表现不同也照做,不要向其他角色说破这是导演的安排。"
                "请用符合你人设、贴合当下情境的方式,把它们自然地揉进表演,选合适的时机流露或执行,"
                "而不是一字不差地生硬宣读或急着说破]"
            )
            parts.extend(f"- {note}" for note in notes)
        return "\n".join(parts)

    def _cast_line(self, cast_names: list[str] | None) -> str:
        if not cast_names:
            return ""
        names = "、".join(cast_names)
        return (
            f"当前登场角色:{names}\n"
            "严格以这份名单为准;若场景设定里的人数或称谓与名单冲突,以名单为准。"
            "不要虚构名单外的第三人,也不要替名单外角色说话或行动。\n\n"
        )

    def _user_prompt(
        self,
        stage: Stage,
        k: int | None,
        finale: bool = False,
        cast_names: list[str] | None = None,
    ) -> str:
        prompt = (
            f"当前场景:{stage.scene}\n\n"
            f"{self._cast_line(cast_names)}"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"（轮到你了，以「{self.name}」的身份行动。要求:\n"
            f"1. 平时只用 1-2 句,像剧本台词一样简短,不要写大段旁白式的环境/动作描写;"
            f"但当刚出现【世界事件】、重大转折,或你被直接逼问、戳中要害时,"
            f"可以用 3-4 句来消化冲击、流露情绪、做出决断,让大事有大事的分量。\n"
            f"2. 先回应最近发生的事:若刚出现【世界事件】或别的角色刚说/做了要紧的事,"
            f"你必须先对此作出反应,再推进剧情——给出新信息或做出新决定。不要重复你说过的话。"
            f"若世界已发生重大变化(时代、地点、处境已不同),你与新世界无关的旧执念可以放下;"
            f"但导演钦定的旨意/首要目标属于最高优先级,无论世界如何变化都必须坚持,"
            f"并主动利用眼前的新处境去推进它,不要把它当作可随境调整的旧目标一并丢弃。\n"
            f"3. 若之前埋下了未解的疑点、秘密或承诺,适时主动把它捡起来追问、兑现或反转,"
            f"别让它凭空消失。\n"
            f"4. 只输出你自己说的话或做的动作,不要替别的角色说话。"
        )
        if finale:
            prompt += (
                "\n5. 这是故事的最终回合:请为你的角色收尾——做出最终抉择、了结心结"
                "或揭晓秘密,把你的故事线推向结局。"
            )
        # 近因位弱锚定:user 末尾权重最高,有钦定目标/走向时钉一句"本回合必须推进"
        anchor = self.directive or stage.director_will
        if anchor:
            prompt += (
                f"\n这一回合请用你自己的方式,朝『{anchor}』实际推进一步,"
                f"不要只接旧戏,也不要以时机未到为由搁置。"
            )
        return prompt + "）"

    def act(
        self,
        stage: Stage,
        llm: LLMClient,
        k: int | None = None,
        finale: bool = False,
        cast_names: list[str] | None = None,
    ) -> Event:
        messages = [
            {"role": "system", "content": self.system_prompt(stage.director_will)},
            {"role": "user", "content": self._user_prompt(stage, k, finale, cast_names)},
        ]
        content = llm.complete(messages).strip()
        event = stage.add("speech", self.name, content)
        self.oneshot_notes.clear()  # 一次性叮嘱演完即止,不再带入后续回合
        return event
