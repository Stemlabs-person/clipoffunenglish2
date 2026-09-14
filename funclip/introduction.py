top_md_1 = ("""
    <div align="center">
    <div style="display:flex; gap: 0.25rem;" align="center">
    FunClip: <a href='https://github.com/modelscope/FunClip'><img src='https://img.shields.io/badge/Github-Code-blue'></a>
    🌟Support us: <a href='https://github.com/modelscope/FunClip/stargazers'><img src='https://img.shields.io/github/stars/modelscope/FunClip.svg?style=social'></a>
    </div>
    </div>

    Built on Alibaba Tongyi Lab's self-developed, open-source [FunASR](https://github.com/modelscope/FunASR) toolkit, using its Paraformer, [Fun-ASR-Nano](https://github.com/QwenAudio/Fun-ASR), and [SenseVoice](https://github.com/QwenAudio/SenseVoice) model families for an open-source pipeline covering speech recognition, endpoint detection, punctuation prediction, timestamp prediction, speaker diarization, and hotword customization.

    Accurate recognition, freely copy the segments you need, or set speaker labels, then clip and add subtitles with one click.

    * Step1: Upload a video or audio file (or try one of the examples below), then click the **<font color="#f7802b">ASR</font>** button
    * Step2: Copy the text you need from the recognition result to the box on the upper right, or set a speaker label, and configure the offset and subtitles (optional)
    * Step3: Click the **<font color="#f7802b">Clip</font>** button or **<font color="#f7802b">Clip+Subtitles</font>** button to get the result

    🔥 FunClip now integrates LLM-powered intelligent clipping - pick an LLM model and give it a try!
    """)

top_md_3 = ("""Visit the FunASR project and paper to learn more about the speech-processing models used in ParaClipper:
    <div align="center">
    <div style="display:flex; gap: 0.25rem;" align="center">
        FunASR: <a href='https://github.com/modelscope/FunASR'><img src='https://img.shields.io/badge/Github-Code-blue'></a>
        FunASR Paper: <a href="https://arxiv.org/abs/2305.11013"><img src="https://img.shields.io/badge/Arxiv-2305.11013-orange"></a>
        🌟Star FunASR: <a href='https://github.com/modelscope/FunASR/stargazers'><img src='https://img.shields.io/github/stars/modelscope/FunASR.svg?style=social'></a>
    </div>
    </div>
    """)

top_md_4 = ("""In the "LLM Clipping" module we offer three ways to call an LLM:
            1. Call a Qwen-series model via the Alibaba Cloud Bailian platform API - you'll need a Bailian API key, get one at [Alibaba Cloud Bailian](https://bailian.console.aliyun.com/#/home);
            2. Choosing a model starting with GPT calls the official OpenAI API - you'll need your own API key and network access;
            3. The [gpt4free](https://github.com/xtekky/gpt4free?tab=readme-ov-file) project is also integrated into FunClip, letting you call GPT models for free through it.

            Options 1 and 2 require entering the corresponding API key in the interface.
            Option 3 can be quite unstable - responses may take a long time or fail to return; feel free to retry, or prepare your own API key and use option 1 or 2 instead.

            Don't open multiple interface tabs on the same port at once - it can make file uploads very slow or freeze entirely. Closing the other tabs resolves this.
            """)
