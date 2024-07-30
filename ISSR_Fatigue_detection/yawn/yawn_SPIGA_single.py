import os
from ultralytics import YOLO
import numpy as np
import cv2
from yawn_utils import yawn_aspect_ratio_SPIGA

from spiga.demo.visualize.plotter import Plotter
from spiga.inference.config import ModelConfig
from spiga.inference.framework import SPIGAFramework

yawn_number=3
no_yawn_number=2


os.makedirs('test',exist_ok=True)
subfolder=['images','labels']
for folder in subfolder:
    os.makedirs(f'test/{folder}',exist_ok=True)

save_image_folder='test/images'
save_label_folder='test/labels'

path_yawn=r'/home/cgi/drive/drowsy_att/YawDD.rar/YAWN/videos/yawn/Mirror_1-FemaleNoGlasses-Yawning.avi'
# path_yawn=r'/home/cgi/drive/drowsy_att/YawDD.rar/YAWN/videos/yawn/5-MaleGlasses.avi'
# path_yawn=r'11-FemaleGlasses.avi.avi'
cap=cv2.VideoCapture(path_yawn)
model_yolo_path=r'/home/cgi/drive/drowsy_att/YawDD.rar/yolov8n-face.pt'
model_eyes_path=r'/home/cgi/drive/drowsy_att/YawDD.rar/eye_detect.pt'
model_yolo=YOLO(model_yolo_path)
model_eyes=YOLO(model_eyes_path)

eyes_dict=model_eyes.names
dataset='wflw'
processor=SPIGAFramework(ModelConfig(dataset))
plotter=Plotter()

while cap.isOpened():
    ret,frame=cap.read()
    if not ret:
        print("End of Video")
        break
    frame2=frame.copy()
    results=model_yolo.predict(frame,conf=0.6)
    result=results[0]
    # Saving image file into the images folder

    for box in result.boxes:
        x0,y0,x1,y1=box.xyxy.cpu().numpy().astype(int)[0]
        cv2.rectangle(frame,(x0,y0),(x1,y1),(255,0,0),2)
        w=abs(x1-x0)
        h=abs(y1-y0)
        bbox=[x0,y0,w,h]
        features=processor.inference(frame,[bbox])
        # Prepare variables
        landmarks=np.array(features['landmarks'][0])
        headpose=np.array(features['headpose'][0])
        x1=round(headpose[0],3)
        x2=round(headpose[1],3)
        x3=round(headpose[2],3)
       
        # # print(headpose)
        frame=plotter.landmarks.draw_landmarks(frame,landmarks,thick=1)
        frame=plotter.hpose.draw_headpose(frame,[x0,y0,x0+w,y0+h],headpose[:3],headpose[3:],euler=True)
        landmarks_int=[landmark.astype('int') for landmark in landmarks]
        yawn_AR=yawn_aspect_ratio_SPIGA(landmarks_int)
        if 'Mirror' in path_yawn:
            if yawn_AR>0.7:
                eyes_results=model_eyes.predict(frame2)
                eyes_result=eyes_results[0]
                video_name=path_yawn.split('/')[-1]
                frame_number=cap.get(cv2.CAP_PROP_POS_FRAMES)
                common_name=f'{video_name}_{frame_number}'
                label_name=common_name+'.txt'
                label_path=os.path.join(save_label_folder,label_name)

                for box_eyes in eyes_result.boxes:
                    eye_class=eyes_dict[box_eyes.cls.cpu().numpy().astype(int)[0]]
                    if eye_class=='awake':
                        eye_number=0
                    else:
                        eye_number=1
                    # x0,y0,x1,y1=box_eyes.xyxy.cpu().numpy().astype(int)[0]
                    xc_eyes,yc_eyes,width_bbox_eyes,height_bbox_eyes=box_eyes.xywhn.cpu().numpy()[0]
                    label_string_eyes=f'{eye_number} {xc_eyes} {yc_eyes} {width_bbox_eyes} {height_bbox_eyes}\n'
                    with open(label_path,'w') as f:
                        f.write(label_string_eyes) 
                image_name=common_name+'.png'
                image_path=os.path.join(save_image_folder,image_name)
               
                cv2.imwrite(image_path,frame2)
                # Saving label .txt file to a label folder
                xc,yc,width_bbox,height_bbox=result.boxes.xywhn.cpu().numpy()[0]
                label_string_yawn=f'{yawn_number} {xc} {yc} {width_bbox} {height_bbox}\n'
                with open(label_path,'a') as f:
                    f.write(label_string_yawn) 
                f.close()
        else:
            if yawn_AR>1.0:
                eyes_results=model_eyes.predict(frame2)
                eyes_result=eyes_results[0]
                video_name=path_yawn.split('/')[-1]
                frame_number=cap.get(cv2.CAP_PROP_POS_FRAMES)
                common_name=f'{video_name}_{frame_number}'
                label_name=common_name+'.txt'
                label_path=os.path.join(save_label_folder,label_name)

                for box_eyes in eyes_result.boxes:
                    eye_class=eyes_dict[box_eyes.cls.cpu().numpy().astype(int)[0]]
                    if eye_class=='awake':
                        eye_number=0
                    else:
                        eye_number=1
                    # x0,y0,x1,y1=box_eyes.xyxy.cpu().numpy().astype(int)[0]
                    xc_eyes,yc_eyes,width_bbox_eyes,height_bbox_eyes=box_eyes.xywhn.cpu().numpy()[0]
                    label_string_eyes=f'{eye_number} {xc_eyes} {yc_eyes} {width_bbox_eyes} {height_bbox_eyes}\n'
                    with open(label_path,'w') as f:
                        f.write(label_string_eyes) 
                
                image_name=common_name+'.png'
                image_path=os.path.join(save_image_folder,image_name)
               
                cv2.imwrite(image_path,frame2)
                # Saving label .txt file to a label folder
                
                xc,yc,width_bbox,height_bbox=result.boxes.xywhn.cpu().numpy()[0]
                label_string_yawn=f'{yawn_number} {xc} {yc} {width_bbox} {height_bbox}\n'
                with open(label_path,'a') as f:
                    f.write(label_string_yawn) 
                f.close()
                

        cv2.putText(frame,f"Yawn Ratio:{yawn_AR}",(20,50),cv2.FONT_HERSHEY_COMPLEX,2,(0,0,0),2)
    
    cv2.imshow('test',frame)
    
    if cv2.waitKey(1) & 0xFF==27:
        print("Quitting the program")
        break
cap.release()
cv2.destroyAllWindows()