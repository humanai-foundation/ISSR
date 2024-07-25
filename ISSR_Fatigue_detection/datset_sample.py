import os
import cv2
import random

save_folder=r'/media/cgi/440A20600A20516A/drowsy_dataset/drowsy_yolo_real'
folder_list=['0_image','10_image']
for folder in folder_list:
    folder_path=os.path.join(save_folder,folder)
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    else:
        print("Folder already exists.")

dir_list=['0','10']
pwd=os.getcwd()
for dir in dir_list:
    folder_path=os.path.join(pwd,dir)
    video_list=os.listdir(folder_path)
    for video in video_list:
        video_path=os.path.join(folder_path,video)
        cap=cv2.VideoCapture(video_path)
        num_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        random_list=[]
        frame_count=0
        while frame_count<300:
            random_frame = random.randint(1,num_frames)
            while random_frame in random_list:
                random_frame=random.randint(1,num_frames)
                
            cap.set(cv2.CAP_PROP_POS_FRAMES,random_frame)
            ret,frame = cap.read()
            current_frame_number = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            
            if not ret:
                break
            image_name=f'{video}_{current_frame_number}.png'
            save_dir_path=os.path.join(save_folder,f'{dir}_image')
            save_image_path=os.path.join(save_dir_path,image_name)
            
            cv2.imwrite(save_image_path,frame)
            frame_count+=1
            random_list.append(random_frame)

        cap.release()


print("Execution Complete!")
        