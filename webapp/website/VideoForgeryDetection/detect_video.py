import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 

import cv2
import numpy as np
from keras.models import load_model

#vid_name = input("\nEnter the name of video: ")
#vid_src = "G:/Video_Forgery_Detection_Using_Machine_Learning/Input_Videos/" + vid_name + ".mp4"

def detect_video_forgery(vid_src):
    vid = []

    sumFrames =0
    cap= cv2.VideoCapture(vid_src)
    
    # Check if video opened successfully
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video file: {vid_src}")
        return {'result': 'Lỗi: Không thể mở video', 'f_frames': 0, 'detail': 'Video codec không được hỗ trợ hoặc file bị lỗi'}
    
    #cap.set(3,240)
    #cap.set(4,320)

    fps = 0

    while(cap.isOpened()):
        ret, frame = cap.read()
        #compressImage = cv2.resize(frame, (0, 0), fx = 0.1, fy = 0.1)
        if ret == False:
            fps = cap.get(cv2.CAP_PROP_FPS)
            break
        b = cv2.resize(frame,(320,240),fx=0,fy=0, interpolation = cv2.INTER_CUBIC)
        sumFrames +=1
        vid.append(b)
    cap.release()
        
    print("\nNo. Of Frames in the Video: ",sumFrames)
    
    # Check if any frames were extracted
    if sumFrames == 0:
        print("[ERROR] No frames extracted from video!")
        return {
            'result': 'Lỗi: Không đọc được video', 
            'f_frames': 0, 
            'detail': 'Video có thể dùng codec AV1 không được hỗ trợ. Vui lòng thử video với codec H.264 (MP4) hoặc H.265 (HEVC).'
        }

    Xtest = np.array(vid)

    print("\nPredicting !! ")
    # Use relative path to model in the project
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    model_path = os.path.join(PROJECT_ROOT, 'models', 'forgery_model_me.hdf5')
    
    # Check if model exists, if not return mock result
    if not os.path.exists(model_path):
        print(f"Warning: Video model not found at {model_path}")
        print("Returning mock result. Please download the video model.")
        return {'result': 'Unknown (Model not found)', 'f_frames': 0}
    
    model = load_model(model_path)
    output = model.predict(Xtest)

    output = output.reshape((-1))
    results = []
    for i in output:
        if i>0.5:
            results.append(1)
        else:
            results.append(0)


    no_of_forged = sum(results)

    print('No of forged----no_of_forged:',no_of_forged)
            
    if no_of_forged <=0:
        print("\nThe video is not forged")
        return {'result':'Authentic','f_frames':0}
        
    else:
        print("\nThe video is forged")
        print("\nNumber of Forged Frames in the video: ",no_of_forged)
        return {'result':'Forged','f_frames':no_of_forged}
