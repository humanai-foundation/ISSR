import os
import random
import shutil
# Making the nesting folders to save the final result in 
os.makedirs('final_dataset',exist_ok=True)
folder_list=['train','valid']
subfolder_list=['images','labels']
for folder in folder_list:
    folder_path=os.path.join('final_dataset',folder)
    os.makedirs(folder_path,exist_ok=True)
    for subfolder in subfolder_list:
        subfolder_path=os.path.join(folder_path,subfolder)
        os.makedirs(subfolder_path,exist_ok=True)

yawn_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/yawn'
no_yawn_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/no_yawn'

yawn_image_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/yawn/images'
no_yawn_image_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/no_yawn/images'

yawn_label_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/yawn/labels'
no_yawn_label_folder=r'/home/cgi/drive/drowsy_att/YawDD.rar/yawnDD_yolo/no_yawn/labels'

yawn_list=os.listdir(yawn_image_folder)
no_yawn_list=os.listdir(no_yawn_image_folder)

yawn_image_count=0
no_yawn_image_count=0
# For yawn_list
random_list=[]
while yawn_image_count<4125:
    random_int=random.randint(0,len(yawn_list)-1)
    while random_int in random_list:
        random_int=random.randint(0,len(yawn_list)-1)
    random_list.append(random_int)
    image=yawn_list[random_int]
    image_name=image.split('.png')[0]
    label_name=image_name+'.txt'
    image_file_path=os.path.join(yawn_image_folder,image)
    label_file_path=os.path.join(yawn_label_folder,label_name)
    if yawn_image_count<3500:
        dest_image_folder='./final_dataset/train/images'
        dest_label_folder='./final_dataset/train/labels'
        dest_image_path=os.path.join(dest_image_folder,image)
        dest_label_path=os.path.join(dest_label_folder,label_name)
        # Copy the images and file
        # shutil.copy(source_file, destination_file)
        shutil.copy(label_file_path,dest_label_path)
        shutil.copy(image_file_path,dest_image_path)
        yawn_image_count+=1
    else:
        dest_image_folder='./final_dataset/valid/images'
        dest_label_folder='./final_dataset/valid/labels'
        dest_image_path=os.path.join(dest_image_folder,image)
        dest_label_path=os.path.join(dest_label_folder,label_name)
        # Copy the images and file
        # shutil.copy(source_file, destination_file)
        shutil.copy(label_file_path,dest_label_path)
        shutil.copy(image_file_path,dest_image_path)
        yawn_image_count+=1

# For the no_yawn list
random_list=[]
while no_yawn_image_count<4125:
    random_int=random.randint(0,len(no_yawn_list)-1)
    while random_int in random_list:
        random_int=random.randint(0,len(no_yawn_list)-1)
    random_list.append(random_int)
    image=no_yawn_list[random_int]
    image_name=image.split('.png')[0]
    label_name=image_name+'.txt'
    image_file_path=os.path.join(no_yawn_image_folder,image)
    label_file_path=os.path.join(no_yawn_label_folder,label_name)
    if no_yawn_image_count<3500:
        dest_image_folder='./final_dataset/train/images'
        dest_label_folder='./final_dataset/train/labels'
        dest_image_path=os.path.join(dest_image_folder,image)
        dest_label_path=os.path.join(dest_label_folder,label_name)
        # Copy the images and file
        # shutil.copy(source_file, destination_file)
        shutil.copy(label_file_path,dest_label_path)
        shutil.copy(image_file_path,dest_image_path)
        no_yawn_image_count+=1
    else:
        dest_image_folder='./final_dataset/valid/images'
        dest_label_folder='./final_dataset/valid/labels'
        dest_image_path=os.path.join(dest_image_folder,image)
        dest_label_path=os.path.join(dest_label_folder,label_name)
        # Copy the images and file
        # shutil.copy(source_file, destination_file)
        shutil.copy(label_file_path,dest_label_path)
        shutil.copy(image_file_path,dest_image_path)
        no_yawn_image_count+=1