import os
import cv2
from ultralytics import YOLO
import torch
import shutil

save_folder=r'/media/cgi/440A20600A20516A/drowsy_dataset/drowsy_label'
os.makedirs(save_folder,exist_ok=True)
folder_list=['0_image','10_image']
subfolder_list=['images','labels']
for folder in folder_list:
    folder_path=os.path.join(save_folder,folder)
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    else:
        print("Folder already exists.")
    for subfolder in subfolder_list:
        subfolder_path=os.path.join(folder_path,subfolder)
        if not os.path.isdir(subfolder_path):
            os.makedirs(subfolder_path)
        else:
            print("Sub-Folder already exists.")

model_path=r'/media/cgi/440A20600A20516A/drowsy_dataset/yolov8n-face.pt'
model=YOLO(model_path)
device='cuda' if torch.cuda.is_available() else 'cpu'
model=model.to(device)

move_folder_path=r'/media/cgi/440A20600A20516A/drowsy_dataset/drowsy_yolo_real'
save_folder_path=r'/media/cgi/440A20600A20516A/drowsy_dataset/drowsy_label'
move_folders=os.listdir(move_folder_path)
for folder in move_folders:
    folder_path=os.path.join(move_folder_path,folder)
    save_subfolder=os.path.join(save_folder_path,folder)
    save_image_path=os.path.join(save_subfolder,'images')
    save_label_path=os.path.join(save_subfolder,'labels')
    class_name=int(folder.split("_")[0][0])
    file_list=os.listdir(folder_path)
    for file in file_list:
        move_file_path=os.path.join(folder_path,file)
        file_name=file.split('.png')[0]
        label_name=f'{file_name}.txt'
        image_destination_path=os.path.join(save_image_path,file)
        label_destination_path=os.path.join(save_label_path,label_name)
        
        img=cv2.imread(move_file_path)
        results=model.predict(img,conf=0.6,device='cuda')
        result=results[0]
        try:
            if len(result.boxes) !=1:
                continue

            label_list=[]
            for box in result.boxes:
                xc,yc,w,h=box.xywhn.cpu().numpy()[0]
                label_list.append(f"{class_name} {xc} {yc} {w} {h}\n")
        
            with open(label_destination_path, 'w') as f:   
                f.writelines(label_list)
            f.close()
            # shutil.copy(source_path, destination_path) (Syntax to use shutil)
            shutil.copy(move_file_path,image_destination_path)
        except:
            print(len(result.boxes))
            print("An error occured!")