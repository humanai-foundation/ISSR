import os
import shutil
path=r'/media/cgi/440A20600A20516A/drowsy_dataset'
folder_list=['0','5','10']

for folder in folder_list:
    folder_path=os.path.join(path,folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Directory '{folder_path}' created successfully.")
    else:
        print(f"Directory '{folder_path}' already exists.")



new_path=r'/home/cgi/drive/drowsy_dataset'
directories=os.listdir(new_path)
move_path=r'/media/cgi/440A20600A20516A/drowsy_dataset'

for directory in directories:
    path=os.path.join(new_path,directory)
    file_list=os.listdir(path)
    for file in file_list:
        class_name=file.split('_')[1].split('.')[0]
        file_path=os.path.join(path,file)
        # print(file_path)
        if class_name=='0':
            destination_path=os.path.join(move_path,'0')
            destination_path=os.path.join(destination_path,file)
            # print(destination_path)
            shutil.copy(file_path,destination_path)
        elif class_name=='5':
            destination_path=os.path.join(move_path,'5')
            shutil.copy(file_path,destination_path)
        else:
            destination_path=os.path.join(move_path,'10')
            shutil.copy(file_path,destination_path)
        
        
        





