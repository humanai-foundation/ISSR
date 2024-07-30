import os
import cv2
import random
from ultralytics import YOLO
save_image_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/no_yawn/images'
save_label_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/no_yawn/labels'

# Importing the YOLO models
model_yolo_path=r'/home/cgi/drive/drowsy_att/YawDD.rar/yolov8n-face.pt'
model_eyes_path=r'/home/cgi/drive/drowsy_att/YawDD.rar/eye_detect.pt'
model_yolo=YOLO(model_yolo_path)
model_eyes=YOLO(model_eyes_path)

eyes_dict=model_eyes.names
no_yawn_number=2

# Folder where the no_yawn videos are saved
video_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/YAWN/videos/no_yawn'
video_list=os.listdir(video_folder)

for video in video_list:
    frame_count=0
    random_list=[]
    video_path=os.path.join(video_folder,video)
    cap=cv2.VideoCapture(video_path)
    total_frames=cap.get(cv2.CAP_PROP_FRAME_COUNT)
    while frame_count<75:
        random_int=random.randint(0,total_frames-1)
        while random_int in random_list:
            random_int=random.randint(0,total_frames-1)
        
        save_image_name=f'{video}_{random_int}.png'
        save_label_name=f'{video}_{random_int}.txt'
        # Creating the save paths for the images
        save_image_path=os.path.join(save_image_folder,save_image_name)
        save_label_path=os.path.join(save_label_folder,save_label_name)  

        cap.set(cv2.CAP_PROP_POS_FRAMES,random_int)
        random_list.append(random_int)
        ret,frame=cap.read()
        label_list=[]
        frame2=frame.copy()
        
        results=model_yolo.predict(frame,conf=0.6)
        eyes_results=model_eyes.predict(frame,conf=0.6)
        eyes_result=eyes_results[0]
        result=results[0]

        for box in result.boxes:
            x0,y0,x1,y1=box.xyxy.cpu().numpy().astype(int)[0]
            xc,yc,width_bbox,height_bbox=result.boxes.xywhn.cpu().numpy()[0]
            label_string_yawn=f'{no_yawn_number} {xc} {yc} {width_bbox} {height_bbox}\n'
            label_list.append(label_string_yawn)
            

            cv2.rectangle(frame,(x0,y0),(x1,y1),(255,0,0),2)
        for box_eyes in eyes_result.boxes:
            eye_class=eyes_dict[box_eyes.cls.cpu().numpy().astype(int)[0]]
            if eye_class=='awake':
                eye_number=0
            else:
                eye_number=1
            x0,y0,x1,y1=box.xyxy.cpu().numpy().astype(int)[0]
            xc_eyes,yc_eyes,width_bbox_eyes,height_bbox_eyes=box_eyes.xywhn.cpu().numpy()[0]
            label_string_eyes=f'{eye_number} {xc_eyes} {yc_eyes} {width_bbox_eyes} {height_bbox_eyes}\n'
            cv2.rectangle(frame,(x0,y0),(x1,y1),(255,0,0),2)
            cv2.putText(frame,eye_class,(x0-10,y0-20),cv2.FONT_HERSHEY_COMPLEX,2,(255,0,255),2)
            label_list.append(label_string_eyes)

        cv2.imshow('no_yawn',frame)
        if cv2.waitKey(1) & 0xff==27:
            print('Quitting the program')
            break
        with open(save_label_path,'w') as f:
            f.writelines(label_list)
        f.close()
        cv2.imwrite(save_image_path,frame2)
        frame_count+=1
    
    cap.release()
    # for box in result.boxes:
    #     x0,y0,x1,y1=box.xyxy.cpu().numpy().astype(int)[0]
    #     cv2.rectangle(frame,(x0,y0),(x1,y1),(255,0,0),2)
    # cv2.imshow('test',frame)
    # cv2.waitKey(0)
cv2.destroyAllWindows()
    