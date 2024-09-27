import os
import cv2
import torch
import clip
from PIL import Image
import pandas as pd
import numpy as np

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-L/14", device=device)

clip_label=[ "driver is combing his or her hair while driving a car",
"driver is reaching behind to the backseat while driving a car",
"driver is talking to the phone in hand while driving a car",
"driver is looking forward with full attention",
"driver is yawning",
"driver is sleeping while driving the car",
"driver is texting while driving the car"]

text = clip.tokenize(clip_label).to(device)


folder_path='/home/ios/dmd_datset'
participant_folder_path=[os.path.join(folder_path,path) for path in os.listdir(folder_path)]
video_path_list=[]
for path in participant_folder_path:
    temp_list=[os.path.join(path,vid_path) for vid_path in os.listdir(path)]
    video_path_list.extend(temp_list)

video_path_list=['gB_6_s5_2019-03-13T13;37;11+01;00_rgb_mosaic.avi']
video_count=0  
# video_path_list=['gA_2_s5_2019-03-13T09;19;23+01;00_rgb_mosaic.avi']
for video in video_path_list:
    cap=cv2.VideoCapture(video)
    column_list=['frame_number','clip_text','conf_score']
    df_distracted=pd.DataFrame(columns=column_list)
    df_drowsy=pd.DataFrame(columns=column_list)
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_count+=1
    video_name=video.split('/')[-1]
    video_type=video_name.split('_')[2]
    print(video_type)
    while cap.isOpened():
        ret,frame=cap.read()
        if not ret:
            print(f'End of video {video_count}')
            break
        frame_body=frame[height//2:,:width//2]  #Front facing camera
        frame_number=cap.get(cv2.CAP_PROP_POS_FRAMES)
        temp_frame=cv2.cvtColor(frame_body,cv2.COLOR_BGR2RGB)
        temp_frame = Image.fromarray(temp_frame, 'RGB')
    
        image = preprocess(temp_frame).unsqueeze(0).to(device)
    
        with torch.no_grad():
            image_features = model.encode_image(image)
            text_features = model.encode_text(text)        
            logits_per_image, logits_per_text = model(image, text)
            probs = logits_per_image.softmax(dim=-1).cpu().numpy()
            # Sort a copy in descending order
            sorted_probs = sorted(probs[0], reverse=True)
            # Second element is the second largest value
            second_index=int(np.where(probs[0]==sorted_probs[1])[0][0])
            first_index=int(np.where(probs[0]==sorted_probs[0])[0][0])

            
            second_string=f'{sorted_probs[1]:.2f} {clip_label[second_index]}'
            
            if clip_label[first_index]=='driver is talking to the phone in hand while driving a car' and sorted_probs[0]>0.85:
                new_value= pd.Series([frame_number,clip_label[first_index],sorted_probs[0]], index=column_list)
                #Putting it in the distracted dataframe
                df_distracted.loc[len(df_distracted)] = new_value
            
            if clip_label[first_index] in ['driver is yawning','driver is sleeping while driving the car'] and video_type=='s5':
                # print('Entered Here!')
                # print(sorted_probs[0])
                new_value= pd.Series([frame_number,clip_label[first_index],sorted_probs[0]], index=column_list)
                df_drowsy.loc[len(df_drowsy)] = new_value
    cap.release()
    if len(df_drowsy)>0 and video_type=='s5':
        csv_path=f'{video_name}.csv'
        # csv_path=f'{video_name}.csv'
        df_drowsy.to_csv(csv_path)
    if len(df_distracted)>0 and video_type in ['s2','s4']:   #To get the simulator and the car videos csv
        csv_path=f'{video_name}.csv'
        # csv_path=f'{video_name}.csv'
        df_distracted.to_csv(csv_path)


print("End of the program!")
        

            
            
        
     
    
    

