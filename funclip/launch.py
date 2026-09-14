#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/alibaba-damo-academy/FunClip). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)

from http import server
import os
import logging
import argparse
import tempfile
from datetime import datetime
import gradio as gr
from funasr import AutoModel
from videoclipper import VideoClipper
from llm.openai_api import openai_call
from llm.qwen_api import call_qwen_model
from llm.g4f_openai_api import g4f_openai_call
from llm.litellm_api import litellm_call
from llm.twelvelabs_api import call_twelvelabs_pegasus
from utils.trans_utils import extract_timestamps
from introduction import top_md_1, top_md_3, top_md_4
from launch_config import build_launch_kwargs


def create_asr_model(model_name, lang, auto_model_cls=AutoModel):
    if model_name == "fun-asr-nano":
        return auto_model_cls(
            model="FunAudioLLM/Fun-ASR-Nano-2512",
            trust_remote_code=True,
            remote_code="./model.py",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            spk_model="cam++",
            hub="hf",
        )
    if model_name == "sensevoice":
        return auto_model_cls(
            model="iic/SenseVoiceSmall",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            spk_model="cam++",
        )

    paraformer_model = (
        "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
        if lang == "zh"
        else "iic/speech_paraformer_asr-en-16k-vocab4199-pytorch"
    )
    return auto_model_cls(
        model=paraformer_model,
        vad_model="damo/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        punc_model="damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        spk_model="damo/speech_campplus_sv_zh-cn_16k-common",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='argparse testing')
    parser.add_argument('--lang', '-l', type=str, default = "zh", help="language mode; selects the Paraformer checkpoint but does not override --model")
    parser.add_argument('--model', '-m', type=str, default="paraformer", choices=["paraformer", "fun-asr-nano", "sensevoice"], help="ASR model: paraformer, fun-asr-nano, or sensevoice (takes precedence over --lang)")
    parser.add_argument('--share', '-s', action='store_true', help="if to establish gradio share link")
    parser.add_argument('--port', '-p', type=int, default=7860, help='port number')
    parser.add_argument('--listen', action='store_true', help="if to listen to all hosts")
    args = parser.parse_args()
    
    funasr_model = create_asr_model(args.model, args.lang)
    audio_clipper = VideoClipper(funasr_model)
    audio_clipper.lang = args.lang
    
    def save_text_to_file(content, extension, output_dir=None):
        if not content:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"result_{timestamp}.{extension}"
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
        else:
            # Create a temporary file
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def audio_recog(audio_input, sd_switch, hotwords, output_dir):
        return audio_clipper.recog(audio_input, sd_switch, None, hotwords, output_dir=output_dir)

    def video_recog(video_input, sd_switch, hotwords, output_dir):
        return audio_clipper.video_recog(video_input, sd_switch, hotwords, output_dir=output_dir)

    def video_clip(dest_text, video_spk_input, start_ost, end_ost, state, output_dir):
        return audio_clipper.video_clip(
            dest_text, start_ost, end_ost, state, dest_spk=video_spk_input, output_dir=output_dir
            )

    def mix_recog(video_input, audio_input, hotwords, output_dir):
        output_dir = output_dir.strip()
        if not len(output_dir):
            output_dir = None
        else:
            output_dir = os.path.abspath(output_dir)
        audio_state, video_state = None, None
        if video_input is not None:
            res_text, res_srt, video_state = video_recog(
                video_input, 'No', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, video_state, None, text_file, srt_file
        if audio_input is not None:
            res_text, res_srt, audio_state = audio_recog(
                audio_input, 'No', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, None, audio_state, text_file, srt_file
    
    def mix_recog_speaker(video_input, audio_input, hotwords, output_dir):
        output_dir = output_dir.strip()
        if not len(output_dir):
            output_dir = None
        else:
            output_dir = os.path.abspath(output_dir)
        audio_state, video_state = None, None
        if video_input is not None:
            res_text, res_srt, video_state = video_recog(
                video_input, 'Yes', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, video_state, None, text_file, srt_file
        if audio_input is not None:
            res_text, res_srt, audio_state = audio_recog(
                audio_input, 'Yes', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, None, audio_state, text_file, srt_file
    
    def mix_clip(dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        output_dir = output_dir.strip()
        if not len(output_dir):
            output_dir = None
        else:
            output_dir = os.path.abspath(output_dir)
        if video_state is not None:
            clip_video_file, message, clip_srt = audio_clipper.video_clip(
                dest_text, start_ost, end_ost, video_state, dest_spk=video_spk_input, output_dir=output_dir)
            return clip_video_file, None, message, clip_srt
        if audio_state is not None:
            (sr, res_audio), message, clip_srt = audio_clipper.clip(
                dest_text, start_ost, end_ost, audio_state, dest_spk=video_spk_input, output_dir=output_dir)
            return None, (sr, res_audio), message, clip_srt
    
    def video_clip_addsub(dest_text, video_spk_input, start_ost, end_ost, state, output_dir, font_size, font_color):
        output_dir = output_dir.strip()
        if not len(output_dir):
            output_dir = None
        else:
            output_dir = os.path.abspath(output_dir)
        return audio_clipper.video_clip(
            dest_text, start_ost, end_ost, state, 
            font_size=font_size, font_color=font_color, 
            add_sub=True, dest_spk=video_spk_input, output_dir=output_dir
            )
        
    def llm_inference(system_content, user_content, srt_text, model, apikey, video_input=None):
        SUPPORT_LLM_PREFIX = ['litellm', 'qwen', 'gpt', 'g4f', 'moonshot', 'deepseek', 'atlascloud', 'minimax', 'pegasus']
        if model.startswith('litellm/'):
            return litellm_call(apikey, model, user_content+'\n'+srt_text, system_content)
        if model.startswith('pegasus'):
            # TwelveLabs Pegasus reasons over the actual video (visuals + audio)
            # rather than the ASR transcript, so it needs the video source.
            if video_input is None:
                logging.error("Pegasus requires a video input; please upload a video first.")
                return "Please upload a video before running Pegasus inference."
            return call_twelvelabs_pegasus(apikey, video_input, model=model, prompt=system_content)
        if model.startswith('qwen'):
            return call_qwen_model(apikey, model, user_content+'\n'+srt_text, system_content)
        if model.startswith('gpt') or model.startswith('moonshot') or model.startswith('deepseek') or model.startswith('atlascloud/') or model.startswith('minimax/'):
            return openai_call(apikey, model, user_content+'\n'+srt_text, system_content)
        elif model.startswith('g4f'):
            model = "-".join(model.split('-')[1:])
            return g4f_openai_call(model, user_content+'\n'+srt_text, system_content)
        else:
            logging.error("LLM name error, only {} are supported as LLM name prefix."
                          .format(SUPPORT_LLM_PREFIX))
    
    def AI_clip(LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        timestamp_list = extract_timestamps(LLM_res)
        output_dir = output_dir.strip()
        if not len(output_dir):
            output_dir = None
        else:
            output_dir = os.path.abspath(output_dir)
        if video_state is not None:
            clip_video_file, message, clip_srt = audio_clipper.video_clip(
                dest_text, start_ost, end_ost, video_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=False)
            return clip_video_file, None, message, clip_srt
        if audio_state is not None:
            (sr, res_audio), message, clip_srt = audio_clipper.clip(
                dest_text, start_ost, end_ost, audio_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=False)
            return None, (sr, res_audio), message, clip_srt
    
    def AI_clip_subti(LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        timestamp_list = extract_timestamps(LLM_res)
        output_dir = output_dir.strip()
        if not len(output_dir):
            output_dir = None
        else:
            output_dir = os.path.abspath(output_dir)
        if video_state is not None:
            clip_video_file, message, clip_srt = audio_clipper.video_clip(
                dest_text, start_ost, end_ost, video_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=True)
            return clip_video_file, None, message, clip_srt
        if audio_state is not None:
            (sr, res_audio), message, clip_srt = audio_clipper.clip(
                dest_text, start_ost, end_ost, audio_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=True)
            return None, (sr, res_audio), message, clip_srt
    
    # gradio interface
    theme = gr.Theme.load("funclip/utils/theme.json")
    with gr.Blocks(theme=theme) as funclip_service:
        gr.Markdown(top_md_1)
        # gr.Markdown(top_md_2)
        gr.Markdown(top_md_3)
        gr.Markdown(top_md_4)
        video_state, audio_state = gr.State(), gr.State()
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    video_input = gr.Video(label="Video Input")
                    audio_input = gr.Audio(label="Audio Input")
                with gr.Column():
                    gr.Examples(['https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/%E4%B8%BA%E4%BB%80%E4%B9%88%E8%A6%81%E5%A4%9A%E8%AF%BB%E4%B9%A6%EF%BC%9F%E8%BF%99%E6%98%AF%E6%88%91%E5%90%AC%E8%BF%87%E6%9C%80%E5%A5%BD%E7%9A%84%E7%AD%94%E6%A1%88-%E7%89%87%E6%AE%B5.mp4', 
                                 'https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/2022%E4%BA%91%E6%A0%96%E5%A4%A7%E4%BC%9A_%E7%89%87%E6%AE%B52.mp4', 
                                 'https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/%E4%BD%BF%E7%94%A8chatgpt_%E7%89%87%E6%AE%B5.mp4'],
                                [video_input],
                                label='Demo Video')
                    gr.Examples(['https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/%E8%AE%BF%E8%B0%88.mp4'],
                                [video_input],
                                label='Multi-speaker Demo Video')
                    gr.Examples(['https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ClipVideo/%E9%B2%81%E8%82%83%E9%87%87%E8%AE%BF%E7%89%87%E6%AE%B51.wav'],
                                [audio_input],
                                label="Demo Audio")
                    with gr.Column():
                        # with gr.Row():
                            # video_sd_switch = gr.Radio(["No", "Yes"], label="👥 Get Speakers", value='No')
                        hotwords_input = gr.Textbox(label="🚒 Hotwords (optional, space-separated, Chinese hotwords only)")
                        output_dir = gr.Textbox(label="📁 File Output Dir (optional, works reliably on Linux/macOS)", value=" ")
                        with gr.Row():
                            recog_button = gr.Button("👂 ASR", variant="primary")
                            recog_button2 = gr.Button("👂👫 ASR+SD")
                video_text_output = gr.Textbox(label="✏️ Recognition Result")
                video_srt_output = gr.Textbox(label="📖 SRT Subtitles")
                with gr.Row():
                    video_text_file = gr.File(label="⬇️ Download Recognition Result", interactive=False)
                    video_srt_file = gr.File(label="⬇️ Download SRT Subtitles", interactive=False)
            with gr.Column():
                with gr.Tab("🧠 LLM Clipping"):
                    with gr.Column():
                        prompt_head = gr.Textbox(label="Prompt System (edit as needed; best not to change the core instructions)", value=("You are a video SRT subtitle analysis and clipping tool. Given a video's SRT subtitles, "
                                "analyze them to find the most exciting, and where possible continuous, segments, and cut them out. Output no more than four segments; merge multiple time-adjacent sentences "
                                "(and their timestamps) within a segment into a single entry. Make sure the text and timestamps match correctly. Output must strictly follow this format: 1. [start time-end time] text, note that the connector is \"-\""))
                        prompt_head2 = gr.Textbox(label="Prompt User (no need to edit; the SRT subtitles below-left are appended automatically)", value=("Here are the SRT subtitles of the video to be clipped:"))
                        with gr.Column():
                            with gr.Row():
                                llm_model = gr.Dropdown(
                                    choices=[
                                        "deepseek-chat",
                                        "qwen-plus",
                                             "gpt-3.5-turbo",
                                             "gpt-3.5-turbo-0125",
                                             "gpt-4-turbo",
                                             "g4f-gpt-3.5-turbo",
                                             "litellm/openai/gpt-4o",
                                             "litellm/anthropic/claude-sonnet-4-6",
                                             "atlascloud/qwen/qwen3.5-flash",
                                             "atlascloud/deepseek-ai/deepseek-v4-pro",
                                             "minimax/MiniMax-M2.7",
                                             "minimax/MiniMax-M2.7-highspeed",
                                             "pegasus1.5"],
                                    value="deepseek-chat",
                                    label="LLM Model Name",
                                    allow_custom_value=True)
                                apikey_input = gr.Textbox(label="APIKEY")
                            llm_button =  gr.Button("LLM Inference (run recognition first; non-g4f models need an API key)", variant="primary")
                        llm_result = gr.Textbox(label="LLM Clipper Result")
                        with gr.Row():
                            llm_clip_button = gr.Button("🧠 AI Clip", variant="primary")
                            llm_clip_subti_button = gr.Button("🧠 AI Clip+Subtitles")
                with gr.Tab("✂️ Text/Speaker Clipping"):
                    video_text_input = gr.Textbox(label="✏️ Text to Clip (join multiple segments with '#')")
                    video_spk_input = gr.Textbox(label="✏️ Speaker to Clip (join multiple speakers with '#')")
                    with gr.Row():
                        clip_button = gr.Button("✂️ Clip", variant="primary")
                        clip_subti_button = gr.Button("✂️ Clip+Subtitles")
                    with gr.Row():
                        video_start_ost = gr.Slider(minimum=-500, maximum=1000, value=0, step=50, label="⏪ Start Offset (ms)")
                        video_end_ost = gr.Slider(minimum=-500, maximum=1000, value=100, step=50, label="⏩ End Offset (ms)")
                with gr.Row():
                    font_size = gr.Slider(minimum=10, maximum=100, value=32, step=2, label="🔠 Subtitle Font Size")
                    font_color = gr.Radio(["black", "white", "green", "red"], label="🌈 Subtitle Color", value='white')
                    # font = gr.Radio(["SimHei", "Alibaba Sans"], label="Font")
                video_output = gr.Video(label="Video Clipped")
                audio_output = gr.Audio(label="Audio Clipped")
                clip_message = gr.Textbox(label="⚠️ Clipping Log")
                srt_clipped = gr.Textbox(label="📖 Clipped SRT Subtitles")
                
        recog_button.click(mix_recog, 
                            inputs=[video_input, 
                                    audio_input, 
                                    hotwords_input, 
                                    output_dir,
                                    ], 
                            outputs=[video_text_output, video_srt_output, video_state, audio_state, video_text_file, video_srt_file])
        recog_button2.click(mix_recog_speaker, 
                            inputs=[video_input, 
                                    audio_input, 
                                    hotwords_input, 
                                    output_dir,
                                    ], 
                            outputs=[video_text_output, video_srt_output, video_state, audio_state, video_text_file, video_srt_file])
        clip_button.click(mix_clip, 
                           inputs=[video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   audio_state, 
                                   output_dir
                                   ],
                           outputs=[video_output, audio_output, clip_message, srt_clipped])
        clip_subti_button.click(video_clip_addsub, 
                           inputs=[video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   output_dir, 
                                   font_size, 
                                   font_color,
                                   ], 
                           outputs=[video_output, clip_message, srt_clipped])
        llm_button.click(llm_inference,
                         inputs=[prompt_head, prompt_head2, video_srt_output, llm_model, apikey_input, video_input],
                         outputs=[llm_result])
        llm_clip_button.click(AI_clip, 
                           inputs=[llm_result,
                                   video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   audio_state, 
                                   output_dir,
                                   ],
                           outputs=[video_output, audio_output, clip_message, srt_clipped])
        llm_clip_subti_button.click(AI_clip_subti, 
                           inputs=[llm_result,
                                   video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   audio_state, 
                                   output_dir,
                                   ],
                           outputs=[video_output, audio_output, clip_message, srt_clipped])
    
    funclip_service.launch(
        **build_launch_kwargs(share=args.share, port=args.port, listen=args.listen)
    )
