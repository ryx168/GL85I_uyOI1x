#!/usr/bin/env python
"""Build the AI 日报 news-broadcast composition.

1. Synthesize every narration unit with edge-tts (cached by text hash).
2. Decode to PCM, concatenate per scene with fixed gaps, write assets/vo/sN.wav.
3. Compute absolute timings for scenes, units (captions) and audio clips.
4. Inject the timing JSON + <audio> clips into tpl/index.tpl.html -> index.html.

Run:  python build.py            (re-uses cached TTS)
      python build.py --force    (regenerate all TTS)
"""
import hashlib, json, os, subprocess, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
VO_DIR = os.path.join(HERE, "assets", "vo")
CACHE = os.path.join(VO_DIR, "cache")
os.makedirs(CACHE, exist_ok=True)

SR = 24000          # edge-tts output rate
GAP = 0.38          # silence between units inside a scene (s)
ANCHOR = "zh-CN-YunyangNeural"    # 新闻 male anchor
ANCHOR2 = "zh-CN-XiaoxiaoNeural"  # 快讯 female anchor
RATE = "+4%"

# ---------------------------------------------------------------- script
# Each scene: id, seg (top-left segment label), voice, leadIn (s before narration),
# tail (s after narration), units: [(zh, en)]
SCRIPT = [
    dict(id="s0", seg="", voice=ANCHOR, leadIn=1.6, tail=0.9, units=[
        ("各位观众晚上好，欢迎收看AI日报。", "Good evening, and welcome to AI Daily."),
        ("今天是2026年11月6日，星期四。", "It's Thursday, November 6, 2026."),
    ]),
    dict(id="s1", seg="今日要闻", voice=ANCHOR, leadIn=0.9, tail=1.0, units=[
        ("今天的头条，来自一场持续三个月的真实实验。", "Today's top story comes from a three-month field experiment."),
        ("一百三十三位专利律师，用了三个月AI之后，", "133 patent lawyers used an AI assistant for three months."),
        ("谁的本领留下来了？", "Afterwards, who kept their skills?"),
    ]),
    dict(id="s2", seg="01 · 头条", voice=ANCHOR, leadIn=0.9, tail=1.0, units=[
        ("研究由麻省理工学院经济学家大卫·奥托团队完成，", "The study is by MIT economist David Autor and co-authors,"),
        ("今年九月发表于美国国家经济研究局工作论文。", "published this September as an NBER working paper."),
        ("十一家美国知识产权律所的一百三十三位律师被随机分组：", "133 lawyers from 11 U.S. IP law firms were randomly split:"),
        ("九十人获得AI起草助手和培训，四十三人作为对照组。", "90 got an AI drafting assistant plus training, 43 were controls."),
        ("三项任务，所有成果都由不知情的资深律师盲评打分。", "Three tasks, all scored blind by expert patent attorneys."),
    ]),
    dict(id="s3", seg="02 · 有 AI 时", voice=ANCHOR, leadIn=0.9, tail=1.0, units=[
        ("先看有AI的时候。", "First, with AI switched on."),
        ("第十天，用AI的律师起草质量高出对照组零点三四个标准差，", "At day 10, AI users out-drafted controls by 0.34 standard deviations,"),
        ("第九十天，差距扩大到零点三八。", "and by day 90 the gap had widened to 0.38."),
        ("新人受益最大，提升零点六；资深律师提升零点三。", "Juniors gained the most, +0.60, versus +0.30 for seniors."),
    ]),
    dict(id="s4", seg="03 · 撤掉 AI", voice=ANCHOR, leadIn=0.9, tail=1.0, units=[
        ("真正的考验在三个月之后。", "The real test came after three months."),
        ("研究人员撤掉AI，让所有人独立修订一份有缺陷的专利申请。", "AI was removed, and everyone redlined a flawed patent application alone."),
        ("整体上，用过AI的律师仍然领先零点三二，", "Overall, the AI group still led by 0.32,"),
        ("但这个优势，几乎全部来自资深律师。", "but that edge came almost entirely from senior lawyers."),
        ("资深律师领先零点四五；新人负零点零三，等于没有差别。", "Seniors: +0.45. Juniors: −0.03, statistically nothing."),
    ]),
    dict(id="s5", seg="04 · 新人分化", voice=ANCHOR, leadIn=0.9, tail=1.0, units=[
        ("更值得注意的是，新人的成绩不是原地踏步，而是两极分化。", "More striking: junior scores didn't stay flat. They split."),
        ("拿到最低档的新人多了二十二个百分点，", "Juniors in the lowest tier rose by 22 percentage points,"),
        ("中等偏下档少了四十二个百分点，高分段同时变多。", "the lower-middle tier fell by 42 points, and the top tier grew."),
        ("研究者的比喻是：AI对一部分新人是跳板，对另一部分是垫子。", "The authors' phrase: a springboard for some juniors, a cushion for others."),
    ]),
    dict(id="s6", seg="05 · 解读", voice=ANCHOR, leadIn=0.9, tail=1.2, units=[
        ("为什么会这样？论文的推测是认知卸载。", "Why? The paper's hypothesis is cognitive offloading."),
        ("新人可能直接接受AI生成的文稿，", "Juniors may accept AI-generated drafts wholesale,"),
        ("跳过了找漏洞、权衡保护范围这些关键判断的练习。", "skipping the judgment calls that build expertise."),
        ("论文的结论只有一句话：基本功，是从AI里学到真本事的前提。", "The conclusion in one line: foundational skill is the prerequisite for learning from AI."),
    ]),
    dict(id="s7", seg="快讯", voice=ANCHOR2, leadIn=0.9, tail=1.0, units=[
        ("再看几条快讯。", "Now, a few quick headlines."),
        ("OpenAI发布网络安全模型GPT-6 Cyber，", "OpenAI released GPT-6 Cyber, a cybersecurity model."),
        ("其智能体在Linux内核找出两千三百零八个潜在漏洞，为九百四十八个写出可用的利用代码。", "Its agents flagged 2,308 potential Linux kernel flaws and built working exploits for 948."),
        ("Meta收购AI编程初创公司Conductor，其云服务将于11月20日关闭。", "Meta acquired AI coding startup Conductor; its cloud service shuts down November 20."),
        ("苹果削减部分工程师的AI日额度，从三百美元降至两百美元。", "Apple cut some engineers' daily AI allowance from $300 to $200."),
        ("Anthropic与美联社签下首个付费内容授权协议。", "Anthropic signed its first paid publisher licensing deal, with the Associated Press."),
        ("DeepSeek在GitHub开源了自主智能体的研究原型。", "DeepSeek open-sourced a research prototype of its autonomous agent on GitHub."),
    ]),
    dict(id="s8", seg="来源", voice=ANCHOR, leadIn=0.9, tail=2.6, units=[
        ("今天头条的完整论文，是美国国家经济研究局第三五七二零号工作论文。", "Today's top story: NBER Working Paper 35720, Autor et al."),
        ("感谢收看，明天见。", "Thanks for watching. See you tomorrow."),
    ]),
]

TICKER = [
    "133 位专利律师实验：同样用 AI，老手增强、新人分化",
    "OpenAI 发布 GPT-6 Cyber：948 个 Linux 内核漏洞写出可用利用代码",
    "Meta 收购 AI 编程初创公司 Conductor",
    "苹果削减工程师 AI 日额度：$300 → $200",
    "Anthropic 与美联社签下首个付费授权协议",
    "DeepSeek 开源自主智能体研究原型",
]

# ---------------------------------------------------------------- tts
def tts(text, voice, force=False):
    key = hashlib.sha1(f"{voice}|{RATE}|{text}".encode("utf-8")).hexdigest()[:14]
    mp3 = os.path.join(CACHE, key + ".mp3")
    raw = os.path.join(CACHE, key + ".raw")
    if force or not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
        # The committed mp3 cache is the fallback: a runner without reachable
        # edge-tts still builds from the cached speech.
        cmd = [sys.executable, "-m", "edge_tts", "--voice", voice, "--rate", RATE,
               "--text", text, "--write-media", mp3]
        subprocess.run(cmd, check=True)
    if force or not os.path.exists(raw) or os.path.getsize(raw) == 0:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-f", "s16le",
                        "-ar", str(SR), "-ac", "1", raw], check=True)
    with open(raw, "rb") as f:
        return f.read()

def trim_silence(pcm, thresh=600, keep=0.12):
    """Trim leading/trailing near-silence, keeping `keep` seconds of pad."""
    import array
    a = array.array("h"); a.frombytes(pcm)
    n = len(a)
    i, j = 0, n
    while i < n and abs(a[i]) < thresh: i += 1
    while j > i and abs(a[j - 1]) < thresh: j -= 1
    pad = int(keep * SR)
    i = max(0, i - pad); j = min(n, j + pad)
    return a[i:j].tobytes()

def main():
    force = "--force" in sys.argv
    t = 0.0
    scenes, captions, audios = [], [], []
    for sc in SCRIPT:
        start = t
        pcm = bytearray()
        units = []
        off = sc["leadIn"]
        for zh, en in sc["units"]:
            u = trim_silence(tts(zh, sc["voice"], force))
            dur = len(u) / 2 / SR
            units.append(dict(zh=zh, en=en, start=round(start + off, 3), end=round(start + off + dur, 3)))
            pcm += u
            pcm += b"\x00" * int(GAP * SR) * 2
            off += dur + GAP
        off -= GAP
        wav = os.path.join(VO_DIR, f"{sc['id']}.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(pcm))
        audio_dur = len(pcm) / 2 / SR
        dur = sc["leadIn"] + off - sc["leadIn"] + sc["tail"]
        dur = round(sc["leadIn"] + (off - sc["leadIn"]) + sc["tail"], 3)
        scenes.append(dict(id=sc["id"], seg=sc["seg"], start=round(start, 3), dur=dur,
                           narStart=round(start + sc["leadIn"], 3), units=units))
        audios.append(f'      <audio id="vo-{sc["id"]}" src="assets/vo/{sc["id"]}.wav" '
                      f'data-start="{round(start + sc["leadIn"], 3)}" data-duration="{round(audio_dur, 3)}" '
                      f'data-track-index="30" data-volume="1"></audio>')
        captions.extend(units)
        t = round(start + dur, 3)
        print(f"{sc['id']}: start {start:7.2f}  dur {dur:6.2f}  narration {audio_dur:6.2f}s")
    total = round(t, 3)
    print(f"TOTAL {total:.2f}s")
    data = dict(total=total, scenes=scenes, captions=captions, ticker=TICKER)
    with open(os.path.join(HERE, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    tpl = open(os.path.join(HERE, "tpl", "index.tpl.html"), encoding="utf-8").read()
    html = (tpl.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
               .replace("<!--__AUDIO__-->", "\n".join(audios))
               .replace("__TOTAL__", str(total)))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote index.html")

if __name__ == "__main__":
    main()
