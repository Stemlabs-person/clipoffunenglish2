#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/alibaba-damo-academy/FunClip). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)

import os
import re
import numpy as np  

PUNC_LIST = ['，', '。', '！', '？', '、', ',', '.', '?', '!']
ASCII_LOWER_TABLE = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
)

def pre_proc(text):
    res = ''
    for i in range(len(text)):
        if text[i] in PUNC_LIST:
            continue
        if '\u4e00' <= text[i] <= '\u9fff':
            if len(res) and res[-1] != " ":
                res += ' ' + text[i]+' '
            else:
                res += text[i]+' '
        else:
            res += text[i]
    if res[-1] == ' ':
        res = res[:-1]
    return res

def proc(raw_text, timestamp, dest_text, lang='zh'):
    # simple matching
    ld = len(dest_text.split())
    normalized_raw_text = raw_text.translate(ASCII_LOWER_TABLE)
    normalized_dest_text = dest_text.translate(ASCII_LOWER_TABLE)
    mi, ts = [], []
    offset = 0
    while True:
        fi = normalized_raw_text.find(
            normalized_dest_text, offset, len(normalized_raw_text)
        )
        ti = raw_text[:fi].count(' ')
        if fi == -1:
            break
        offset = fi + len(normalized_dest_text)
        mi.append(fi)
        ts.append([timestamp[ti][0]*16, timestamp[ti+ld-1][1]*16])
    return ts
            

def proc_spk(dest_spk, sd_sentences):
    ts = []
    for d in sd_sentences:
        d_start = d['timestamp'][0][0]
        d_end = d['timestamp'][-1][1]
        spkid=dest_spk[3:]
        if str(d['spk']) == spkid and d_end-d_start>999:
            ts.append([d_start*16, d_end*16])
    return ts

def generate_vad_data(data, sd_sentences, sr=16000):
    assert len(data.shape) == 1
    vad_data = []
    for d in sd_sentences:
        d_start = round(d['ts_list'][0][0]/1000, 2)
        d_end = round(d['ts_list'][-1][1]/1000, 2)
        vad_data.append([d_start, d_end, data[int(d_start * sr):int(d_end * sr)]])
    return vad_data

def write_state(output_dir, state):
    for key in ['/recog_res_raw', '/timestamp', '/sentences']:#, '/sd_sentences']:
        with open(output_dir+key, 'w') as fout:
            fout.write(str(state[key[1:]]))
    if 'sd_sentences' in state:
        with open(output_dir+'/sd_sentences', 'w') as fout:
            fout.write(str(state['sd_sentences']))

def load_state(output_dir):
    state = {}
    with open(output_dir+'/recog_res_raw') as fin:
        line = fin.read()
        state['recog_res_raw'] = line
    with open(output_dir+'/timestamp') as fin:
        line = fin.read()
        state['timestamp'] = eval(line)
    with open(output_dir+'/sentences') as fin:
        line = fin.read()
        state['sentences'] = eval(line)
    if os.path.exists(output_dir+'/sd_sentences'):
        with open(output_dir+'/sd_sentences') as fin:
            line = fin.read()
            state['sd_sentences'] = eval(line)
    return state

def convert_pcm_to_float(data):
    if data.dtype == np.float64:
        return data
    elif data.dtype == np.float32:
        return data.astype(np.float64)
    elif data.dtype == np.int16:
        bit_depth = 16
    elif data.dtype == np.int32:
        bit_depth = 32
    elif data.dtype == np.int8:
        bit_depth = 8
    else:
        raise ValueError("Unsupported audio data type")

    # Now handle the integer types
    max_int_value = float(2 ** (bit_depth - 1))
    if bit_depth == 8:
        data = data - 128
    return (data.astype(np.float64) / max_int_value)

def convert_time_to_millis(time_str):
    # Format: [hours:minutes:seconds,milliseconds]
    hours, minutes, seconds, milliseconds = map(int, re.split('[:,]', time_str))
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

def extract_timestamps(input_text):
    # Use a regex to find every timestamp
    timestamps = re.findall(r'\[(\d{2}:\d{2}:\d{2},\d{2,3})\s*-\s*(\d{2}:\d{2}:\d{2},\d{2,3})\]', input_text)
    times_list = []
    print(timestamps)
    # Loop over every timestamp found and convert it to milliseconds
    for start_time, end_time in timestamps:
        start_millis = convert_time_to_millis(start_time)
        end_millis = convert_time_to_millis(end_time)
        times_list.append([start_millis, end_millis])
    
    return times_list


if __name__ == '__main__':
    text = ("1. [00:00:00,500-00:00:05,850] In our inclusive design work, there's a project I love talking about called Searching for Beauty Far Away."
    "2. [00:00:07,120-00:00:12,940] In this project, which we call Searching for Beauty, we combined it with rural revitalization, drawing on our design capabilities."
    "3. [00:00:13,240-00:00:25,620] Using our own staff's design skills and the skills of our design ecosystem partners, we help rural revitalization partners who want to bring their products, including processed agricultural products, to market,")

    print(extract_timestamps(text))
