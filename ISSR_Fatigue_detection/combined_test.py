import asyncio
import cv2
import time
from ultralytics import YOLO
import mediapipe as mp
from drowsy_mediapipe_utils import *


async def yolo_process(model_yolo,frame_yolo,class_dict):
        frame_yolo=cv2.cvtColor(frame_yolo,cv2.COLOR_BGR2GRAY)
        frame_yolo=cv2.cvtColor(frame_yolo,cv2.COLOR_GRAY2RGB)
        results_yolo=model_yolo.predict(frame_yolo,verbose=False,classes=[0,1,5])
        result_yolo=results_yolo[0]
        result_list=[]
        for box in result_yolo.boxes:
            class_index=box.cls.cpu().numpy().astype(int)[0]
            conf=box.conf.cpu().numpy()[0]
            conf=str(round(conf,2))
            class_name=class_dict[class_index]
            class_final=f'{class_name}: {conf}'
            x0,y0,x1,y1=box.xyxy.cpu().numpy().astype(int)[0]
            result_list.append([x0,y0,x1,y1,class_final])
            
        return result_list
            
async def mediapipe_process(landmarker,frame_front,frame_timestamp_ms,width,height):
    frame_front=np.array(frame_front)
    # Left eyes indices 
    LEFT_EYE =[ 362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385,384, 398 ]
    # right eyes indices
    RIGHT_EYE=[ 33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161 , 246 ]  
    draw=True
    
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_front)
    result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)
    ear_ratio=None
    if len(result.face_landmarks)>0:
        mesh_coord = [(int(point.x * width//2), int(point.y * height//2)) for point in result.face_landmarks[0]]
        if draw :
            [cv2.circle(frame_front, mesh_coord[i], 2, (0,255,0), -1) for i in range(len(mesh_coord)) if (i in LEFT_EYE) or  (i in RIGHT_EYE)]
    # frame_new=draw_landmarks_on_image(frame_front,face_landmarker_result)
        ear_ratio=blinkRatio(landmarks=mesh_coord,right_indices=RIGHT_EYE,left_indices=LEFT_EYE)
        ear_ratio=round(ear_ratio,2)
        # Add text to the image
        # cv2.putText(img, text, (x, y), font, fontScale, color, thickness, lineType)
        text=f'EAR_ratio:{ear_ratio}'
        cv2.putText(frame_front,text,(20,50),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
    
        
    return [frame_front,ear_ratio] 

async def main(video_path,model_path,yolo_model_path):
    #model path is the mediapipe model path
    #Loading the YOLO model
    model_distraction=YOLO(yolo_model_path)
    class_dict=model_distraction.names
    
    cap=cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
   
    BaseOptions = mp.tasks.BaseOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    # Create a face landmarker instance with the video mode:
    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=VisionRunningMode.VIDEO)

    landmarker=FaceLandmarker.create_from_options(options)
    
    while cap.isOpened():
        s = time.perf_counter()
        ret,frame=cap.read()
        if not ret:
            print('End of Video')
            break
        frame_front=frame[height//2:,:width//2]  #Front facing camera
        frame_yolo=frame_front.copy() #Frame that is passed to the YOLO model
        frame_timestamp_ms= int(cap.get(cv2.CAP_PROP_POS_MSEC))
        
        process_mediapipe = asyncio.create_task(mediapipe_process(landmarker=landmarker,frame_front=frame_front,frame_timestamp_ms=frame_timestamp_ms,width=width,height=height))
        process_yolo = asyncio.create_task(yolo_process(model_yolo=model_distraction,frame_yolo=frame_yolo,class_dict=class_dict))
        
        result = await asyncio.gather(process_mediapipe, process_yolo)
        frame_new=result[0][0]
        ear_ratio=result[0][1]
        result_list=result[1]
        
        if len(result_list)>0:
            x0,y0,x1,y1,class_final=result_list[0]
            print(type(frame_new))
            cv2.rectangle(frame_new,(x0,y0),(x1,y1),(0,255,0),2)
            cv2.putText(frame_new,class_final,(x0-20,y0-20),cv2.FONT_HERSHEY_COMPLEX,1,(0,0,255),2)
            
        
        elapsed = time.perf_counter() - s
        # print(f"{__file__} executed in {elapsed:0.2f} seconds.")
        fps=1/elapsed
        fps_str=f'FPS: {fps:0.2f}'
        # print(fps_str)
        height_new,width_new,n_channels=frame_new.shape
        cv2.putText(frame_new,fps_str,(width_new-200,20),cv2.FONT_HERSHEY_COMPLEX,0.75,(255,255,0),2)
        
        cv2.imshow('Driver Front View',frame_new)
        
        if cv2.waitKey(1) & 0xFF==27:
            print('Quitting the program')
            break
    
    cap.release()
    cv2.destroyAllWindows()
    

if __name__ == "__main__":
    
    video_path='gZ_31_s2_2019-04-08T09;35;25+02;00_rgb_mosaic.avi'
    model_yolo='models/best.pt'
    model_mediapipe='models/face_landmarker.task'
    asyncio.run(main(video_path=video_path,model_path=model_mediapipe,yolo_model_path=model_yolo))
    
    
