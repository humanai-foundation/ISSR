import os
import random
import shutil

yolo_folder=r'/media/cgi/440A20600A20516A/drowsy_dataset/uta_rldd_yolo'
os.makedirs(yolo_folder,exist_ok=True)

folder_list=['train','test','valid']
subfolder_list=['images','labels']

for folder in folder_list:
    folder_path=os.path.join(yolo_folder,folder)
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


move_folder_path=r'/media/cgi/440A20600A20516A/drowsy_dataset/drowsy_label'
save_folder_path=r'/media/cgi/440A20600A20516A/drowsy_dataset/uta_rldd_yolo'
move_folders=os.listdir(move_folder_path)
train_list=[]
val_list=[]
test_list=[]

#Setting the train folder path
train_folder_path=os.path.join(save_folder_path,'train')
train_image_path=os.path.join(train_folder_path,'images')
train_label_path=os.path.join(train_folder_path,'labels')

#Setting the valid folder path
valid_folder_path=os.path.join(save_folder_path,'valid')
valid_image_path=os.path.join(valid_folder_path,'images')
valid_label_path=os.path.join(valid_folder_path,'labels')

#Setting the test folder path
test_folder_path=os.path.join(save_folder_path,'test')
test_image_path=os.path.join(test_folder_path,'images')
test_label_path=os.path.join(test_folder_path,'labels')

for folder in move_folders:
    number_done_list=[]
    image_count=0
    folder_path=os.path.join(move_folder_path,folder)
    subfolder_path=os.path.join(folder_path,'images')
    file_list=os.listdir(subfolder_path)
    total_images=len(file_list)
    train_split=int(0.7*total_images)
    val_split=int(0.15*total_images)
    test_split=total_images-train_split-val_split
    file_num=[i for i in range(len(file_list))]

    move_folder_class=os.path.join(move_folder_path,folder)  #move_folder_path + /0_image
    move_folder_images=os.path.join(move_folder_class,'images') #move_folder_path + /0_image/images
    move_folder_labels=os.path.join(move_folder_class,'labels')

    while image_count<train_split:
        random_number = random.randint(0,total_images-1)
        while random_number in number_done_list:
            random_number=random.randint(0,total_images-1)
        
        image_file=file_list[random_number]
        label_file=file_list[random_number].split('.png')[0]+'.txt'

        move_file_path=os.path.join(move_folder_images,image_file)  #move_folder_path +0_image/images/<image_path>
        move_label_path=os.path.join(move_folder_labels,label_file)

        train_image_file=os.path.join(train_image_path,image_file)
        train_label_file=os.path.join(train_label_path,label_file)

        # shutil.copy(source_path, destination_path) (Syntax to use shutil)
        shutil.copy(move_file_path,train_image_file)
        shutil.copy(move_label_path,train_label_file)

        train_list.append(file_list[random_number])
        number_done_list.append(random_number)
        image_count+=1

    image_count=0  #Setting it to 0 to get the files for the val folder
    while image_count<val_split:
        random_number = random.randint(0,total_images-1)
        while random_number in number_done_list:
            random_number=random.randint(0,total_images-1)

        image_file=file_list[random_number]
        label_file=file_list[random_number].split('.png')[0]+'.txt'

        move_file_path=os.path.join(move_folder_images,image_file)  #move_folder_path +0_image/images/<image_path>
        move_label_path=os.path.join(move_folder_labels,label_file)

        valid_image_file=os.path.join(valid_image_path,image_file)
        valid_label_file=os.path.join(valid_label_path,label_file)

        shutil.copy(move_file_path,valid_image_file)
        shutil.copy(move_label_path,valid_label_file)

        val_list.append(file_list[random_number])
        number_done_list.append(random_number)
        image_count+=1

    test_num=list(set(file_num)-set(number_done_list))
    for num in test_num:
        image_file=file_list[num]
        label_file=file_list[num].split('.png')[0]+'.txt'

        move_file_path=os.path.join(move_folder_images,image_file)  #move_folder_path +0_image/images/<image_path>
        move_label_path=os.path.join(move_folder_labels,label_file)

        test_image_file=os.path.join(test_image_path,image_file)
        test_label_file=os.path.join(test_label_path,label_file)

        shutil.copy(move_file_path,test_image_file)
        shutil.copy(move_label_path,test_label_file)
       
        test_list.append(file_list[num])

# Check to see if the dataset was created correctly
folder_path=r'/media/cgi/440A20600A20516A/drowsy_dataset/uta_rldd_yolo'
folder_list=os.listdir(folder_path)
train_list=[]
val_list=[]
test_list=[]
for folder in folder_list:
    new_folder=os.path.join(folder_path,folder)
    # print(new_folder)
    subfolder_list=os.listdir(new_folder)
    label_folder_path=os.path.join(new_folder,'labels')
    label_files_png=set([file.split('.txt')[0]+'.png' for file in os.listdir(label_folder_path)])
    image_folder_path=os.path.join(new_folder,'images')
    image_list=set(os.listdir(image_folder_path))

    if folder =='train':
        train_list=os.listdir(image_folder_path).copy()
    elif folder=='valid':
        val_list=os.listdir(image_folder_path).copy()
    else:
        test_list=os.listdir(image_folder_path).copy()

    if len(label_files_png-image_list)!=0:
        print("Some error occured")
    else:
        print("Dataset looks fine!")


print(set(train_list).isdisjoint(test_list))
print(set(train_list).isdisjoint(val_list))
print(set(test_list).isdisjoint(val_list))
