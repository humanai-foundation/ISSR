import clip
import torch
import cv2
from PIL import Image
import uuid
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

video_path='gA_1_s2_2019-03-08T09;21;03+01;00_rgb_mosaic.avi'
# video_path='/home/ios/drive/clip_test/gA_5_s5_2019-03-13T09;06;49+01;00_rgb_mosaic.avi'
cap=cv2.VideoCapture(video_path)
width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

#Saving the zero shot video from clip video
fileid=uuid.uuid4()
resize_width=640
resize_height=480
# fps=cap.get(cv2.CAP_PROP_FPS)
fps=5
record_path=f'clip_model_test_{fileid}.mp4'
fourcc=cv2.VideoWriter_fourcc(*'mp4v')
video_write=cv2.VideoWriter(record_path, fourcc,fps, (resize_width,resize_height))

while cap.isOpened():
    ret,frame=cap.read()
    if not ret:
        print("End of Video")
        break
    
    # frame_body=frame[height//2:,:width//2]  #Front facing camera
    frame_body=frame[height//2:,width//2:] #Side-view camera
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
        # cv2.putText(img, text, org, font, fontScale, fontColor, thickness, cv2.LINE_AA) 
        first_string=f'{sorted_probs[0]:.2f} {clip_label[first_index]}'
        second_string=f'{sorted_probs[1]:.2f} {clip_label[second_index]}'
        cv2.putText(frame_body,first_string,(20,30),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,0),2,cv2.LINE_AA)
        cv2.putText(frame_body,second_string,(20,70),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),2,cv2.LINE_AA)
      
    frame_body=cv2.resize(frame_body,(resize_width,resize_height))  
    video_write.write(frame_body)
    cv2.imshow('test',frame_body)
    if cv2.waitKey(1) & 0xFF==27:
        print("Quitting the program")
        break

cap.release()
video_write.release()
cv2.destroyAllWindows()