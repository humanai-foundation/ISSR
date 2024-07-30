import os
import cv2
import shutil
os.makedirs('YAWN',exist_ok=True)
subfolder=['images','videos']
for folder in subfolder:
    os.makedirs(f'YAWN/{folder}',exist_ok=True)
    if folder=='videos':
        os.makedirs(f'YAWN/{folder}/no_yawn',exist_ok=True)
        os.makedirs(f'YAWN/{folder}/yawn',exist_ok=True)
HOME='YawDD dataset'
dir_list=[dir for dir in os.listdir(HOME) if os.path.isdir(os.path.join(HOME,dir))]
for dir in dir_list:
    dir_path=os.path.join(HOME,dir)
    if dir=='Dash':
        subfolder_list=os.listdir(dir_path)
        for subfolder in subfolder_list:
            subfolder_path=os.path.join(dir_path,subfolder)
            video_list=os.listdir(subfolder_path)
            for video in video_list:
                video_path=os.path.join(subfolder_path,video)
                save_folder_path='YAWN/videos/yawn'
                dst_path=os.path.join(save_folder_path,video)
                # shutil.copy(src, dst)
                shutil.copy(video_path,dst_path)

    else:
        subfolder_list=os.listdir(dir_path)
        for subfolder in subfolder_list:
            subfolder_path=os.path.join(dir_path,subfolder)
            video_list=os.listdir(subfolder_path)
            for video in video_list:
                video_path=os.path.join(subfolder_path,video)
                if '-Yawning' in video:
                    save_folder_path='YAWN/videos/yawn'
                    dst_video_name=f'{dir}_{video}'
                    dst_path=os.path.join(save_folder_path,dst_video_name)
                    # dst_path=os.path.join(save_folder_path,video)
                    # shutil.copy(src, dst)
                    shutil.copy(video_path,dst_path)
                elif '-Talking' in video:
                    save_folder_path='YAWN/videos/no_yawn'
                    dst_video_name=f'{dir}_{video}'
                    dst_path=os.path.join(save_folder_path,dst_video_name)
                    # shutil.copy(src, dst)
                    shutil.copy(video_path,dst_path)
                # print(video)