#import mutagen
#from mutagen.mp3 import MP3
#from mutagen.flac import FLAC
#import threading
import os
#import sys
#import time
import utils
#from tkinter import ttk
#import customtkinter
#import customtkinter as ctk
from pathlib import Path
#from itertools import chain
import database



# def import_player(full_path, audio, tec_audio_info_num, file_name):
#     player = utils.create_player(full_path)
#     player.play()
#     print(utils.get_audio_info(audio, tec_audio_info_num))
#     print(utils.get_audio_tags(audio, file_name))
#     # Даем время на инициализацию потока
#     time.sleep(0.5)
#     return player

# def temp(file_path): #временный выбор музыки
#     p = Path('./music/used')
#     a = list(chain(p.glob('**/*.mp3'), p.glob('**/*.wav'), p.glob('**/*.mp4'), \
#     p.glob('**/*.flac'),p.glob('**/*.ogg')))
    
#     for i in range(len(a)):
#         cut_music_names = str(a[i])[len(file_path)+1:]
#         print(f"[{i}] {cut_music_names}")
#     print("Выбери файл и впиши его номер")
#     inp = int(input())
#     file_name = str(a[inp])[len(file_path)+1:]
#     print(file_name)
#     return file_name


if __name__ == "__main__":
    
    # путь к папке VLC движка
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vlc_dir = utils.import_VLC(base_dir)

    #file_path = "music/used"
    #file_name = temp(file_path)
    
    database.create_queue()
    database.pl_app()
 
    # file_path, file_name, full_path = utils.import_paths(base_dir,file_name)
    # audio = mutagen.File(full_path)
    # tec_audio_info_num = utils.tec_info(full_path, audio)
    # player = import_player(full_path, audio, tec_audio_info_num, file_name)
    # details = utils.get_audio_info(audio, tec_audio_info_num)
    # tags = utils.get_audio_tags(audio, file_name)
        
    #total_sec = audio.info.length // 1000
    #if total_sec == 0: total_sec = 1
    
    import ui_utils
    #ui_utils.init_data(player=None, tags=None, details=None, total_sec=0)

    from gui2 import App