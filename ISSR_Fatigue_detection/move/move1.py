import os
import shutil
current_path=os.getcwd()
path=os.path.join(current_path,'archive')
folders=os.listdir(path)
destination_path=r'/home/cgi/drive/drowsy_dataset'
for folder in folders:
    folder_path=os.path.join(path,folder)
    directories=os.listdir(folder_path)
    for directory in directories:
        middle_path=os.path.join(folder_path,directory)
        for dir in os.listdir(middle_path):
            final_path=os.path.join(middle_path,dir)
            shutil.move(final_path,destination_path)


