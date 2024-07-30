import os
new_path=r'/home/cgi/drive/drowsy_dataset'
directories=os.listdir(new_path)
for directory in directories:
    path=os.path.join(new_path,directory)
    file_list=os.listdir(path)
    for file in file_list:
        file_path=os.path.join(path,file)
        new_name=f'{directory}_{file}'
        rename_path=os.path.join(path,new_name)
        os.rename(file_path, rename_path)