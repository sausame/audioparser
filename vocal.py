#!/usr/bin/env python
# -*- coding:utf-8 -*-

from pydub import AudioSegment
from pydub.silence import detect_silence

import csv
import os
import stat
import sys
import subprocess
import time


def getch():
    sys.stdin.read(1)


def chmod(path, mode=stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH):
    if os.path.exists(path):
        try:
            os.chmod(path, mode)
        except PermissionError as e:
            print(e)

def get_all_pathnames(dirpath, suffix=None):

    pathnames = list()

    for root, dirs, files in os.walk(dirpath, topdown=False):
        for name in files:
            if suffix is not None and not name.endswith(suffix):
                continue

            pathname = os.path.join(root, name)
            pathnames.append(pathname)

    pathnames = sorted(pathnames)

    return pathnames

def cut_audio_file(dest_file_path, audio_file_path, start, duration):

    s1 = int(start / 1000)
    ms1 = start % 1000

    s2 = int(duration / 1000)
    ms2 = duration % 1000

    cmd = ['ffmpeg',
           '-y',
           '-i',
           audio_file_path,
           '-ss',
           '{}.{:03d}'.format(s1, ms1),
           '-t',
           '{}.{:03d}'.format(s2, ms2),
           '-c',
           'copy',
           dest_file_path]

    result = subprocess.run(cmd, capture_output=True, text=True)

    error = result.stdout
    if error and len(error) > 0:
        print(error)


def run_command(cmd, shell=False):

    process = subprocess.Popen(
        cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    output, unused_err = process.communicate()
    retcode = process.poll()

    if retcode != 0:
        raise subprocess.CalledProcessError(retcode, cmd)

    return output


def get_path_prefix(pathname):

    pos = pathname.rfind('.')

    if pos <= 0:
        return pathname

    return pathname[:pos]

def get_csv_pathname(audio_file_path, name=None):

    prefix = get_path_prefix(audio_file_path)

    if name and len(name) > 0:
        pathname = '{}.{}.csv'.format(prefix, name)
    else:
        pathname = '{}.csv'.format(prefix)

    return pathname


def save_chunks(chunks, audio_file_path, name=None):

    pathname = get_csv_pathname(audio_file_path, name)

    with open(pathname, '+w', newline='') as fp:
        writer = csv.writer(fp, delimiter='\t')

        for index in range(len(chunks)):
            chunk = chunks[index]

            values = [index + 1, chunk[0], chunk[1]]
            writer.writerow(values)
        
        print('Save', len(chunks), 'into', pathname)


def translate_chunks_to_commands(chunks, audio_file_path, separate_times=1):

    if not chunks:
        return None

    commands = []
    for index in range(len(chunks)):
        chunk = chunks[index]

        start = chunk[0]
        s1 = int(start / 1000)
        ms1 = start % 1000

        end = chunk[1]
        s2 = int(end / 1000)
        ms2 = end % 1000

        if index > 0 and index % separate_times == 0:
            command = 'read -n 1 -s -r -p "Press any key to continue"'
            commands.append(command)
            command = '\n\n'

        commands.append('echo {} {}.{:03d}, {}.{:03d}'.format(
            index + 1, s1, ms1, s2, ms2))
        commands.append('ffplay -ss {}.{:03d} -t {}.{:03d} -autoexit {} 2>>/dev/null'.format(
            s1, ms1, s2, ms2, audio_file_path))

    return commands


def save_chunks_to_shell_script(chunks, audio_file_path, separate_times=1):

    commands = translate_chunks_to_commands(
        chunks, audio_file_path, separate_times)

    if not commands:
        return None

    prefix = get_path_prefix(audio_file_path)
    pathname = '{}.sh'.format(prefix)

    with open(pathname, '+w', newline='') as fp:
        fp.write('#!/bin/sh\n\n')
        for command in commands:
            fp.write(command + '\n')

    chmod(pathname)

    return pathname

# silence_threshold: the silence threshold (in dBFS)


def find_silent_chunks(audio_file_path, min_silence_len=1000, silence_threshold=-42):
    # Load the audio file
    audio = AudioSegment.from_mp3(audio_file_path)

    # Detect silent chunks in the audio
    return detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_threshold)


def find_vocal_chunks(silent_chunks):

    vocal_trucks = []
    last_end = None

    for chunk in silent_chunks:
        if last_end:
            duration = chunk[0] - last_end
            vocal_truck = (last_end, duration)
            vocal_trucks.append(vocal_truck)

        last_end = chunk[1]

    return vocal_trucks


def find_valid_chunks(audio_file_path, start_index=0, min_silence_len=1000):

    silent_chunks = find_silent_chunks(
        audio_file_path, min_silence_len=min_silence_len)

    vocal_chunks = find_vocal_chunks(silent_chunks)

    if start_index == 0:
        return vocal_chunks

    if len(vocal_chunks) <= start_index:
        return

    return vocal_chunks[start_index:]


def find_valid_chunks_in_period(audio_file_path, start, duration, min_silence_lens):

    old_start = start
    old_duration = duration

    temp_path = 'TEMP.mp3'

    start -= min_silence_lens[0]
    duration += 2 * min_silence_lens[0]
    cut_audio_file(temp_path, audio_file_path, start, duration)

    chunks = find_valid_chunks(
        temp_path, start_index=0, min_silence_len=min_silence_lens[1])

    if len(chunks) == 1:
        return [[old_start, old_duration]]

    new_chunks = []
    for chunk in chunks:
        new_chunks.append([chunk[0] + start, chunk[1]])

    print('------------------------------')
    print(old_start, old_duration)
    print(new_chunks)

    return new_chunks


# vocal_offset: add an offset to provent lost of the beginning and ending
def percisely_find_valid_chunks(audio_file_path,
                                start_index=0,
                                separate_times=1,
                                max_duration=1000,
                                min_silence_lens=[1000, 600],
                                vocal_offset=200):

    chunks = find_valid_chunks(
        audio_file_path, start_index=start_index, min_silence_len=min_silence_lens[0])

    valid_chunks = []

    for chunk in chunks:
        start = chunk[0]
        duration = chunk[1]

        if duration < max_duration:
            valid_chunks.append(
                [start - vocal_offset, duration + 2 * vocal_offset])
            continue

        new_chunks = find_valid_chunks_in_period(
            audio_file_path, start, duration, min_silence_lens)

        for new_chunk in new_chunks:
            start = new_chunk[0]
            duration = new_chunk[1]
            valid_chunks.append(
                [start - vocal_offset, duration + 2 * vocal_offset])

    save_chunks(valid_chunks, audio_file_path)
    save_chunks_to_shell_script(valid_chunks, audio_file_path, separate_times)

    if len(valid_chunks) % separate_times == 0:
        return

    print('Found an error when parsing', audio_file_path)


def parse_file(audio_file_path, separate_times=1, start_index=3, force=False):

    csv_pathname = get_csv_pathname(audio_file_path)

    if not force and os.path.exists(csv_pathname):
        return

    print('Parsing', audio_file_path, '...')

    percisely_find_valid_chunks(
        audio_file_path, start_index=start_index, separate_times=separate_times)

def parse_dir(dirname, separate_times=1):

    pathnames = get_all_pathnames(dirname, '.mp3')
    for pathname in pathnames:
        parse_file(pathname, separate_times)

def parse(pathname, separate_times=1):

    if os.path.isdir(pathname): 
        parse_dir(pathname, separate_times)
    else:
        parse_file(pathname, separate_times, force=True)

def main(argv):

    num = len(argv)

    if num < 2:
        print('Usage:\n\t', argv[0], 'AUDIO-FILE-PATH [SEPARATE-TIMES]\n')
        exit()

    os.environ['TZ'] = 'Asia/Shanghai'
    time.tzset()

    pathname = os.path.realpath(argv[1])

    if num > 2:
        separate = int(argv[2])
    else:
        separate = 1

    parse(pathname, separate)


if __name__ == '__main__':
    main(sys.argv)
