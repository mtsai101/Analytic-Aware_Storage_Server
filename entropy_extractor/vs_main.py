import multiprocessing as mp
from multiprocessing import Pool
from color import get_color_entropy
from edge import get_edge_entropy
from conv import get_conv_entropy
from conv import get_temp_conv_entropy
from influxdb import InfluxDBClient
from CUDA_background import ProcVid1, ProcFrameCuda3
from shot_detection import ShotDetector
import threading
import time
import os 
import concurrent.futures
import ast 
import yaml

with open('/home/min/Multi-level-Feature-Driven-Storage-Server/configuration_manager/config.yaml','r') as yamlfile:
    data = yaml.load(yamlfile,Loader=yaml.FullLoader)

DBclient = InfluxDBClient(host=data['global']['database_ip'], port=data['global']['database_port'], database=data['global']['database_name'], username='root', password='root')

def background_subtraction(pending_tuple):
    proc_frame_cuda3 = ProcFrameCuda3()
    ProcVid1(proc_frame_cuda3, pending_tuple[0], pending_tuple[1])
    del proc_frame_cuda3

def launch_shot_detector(pending_tuple):
    try:

        st = time.time()
        shotDetector = ShotDetector()
        shotDetector.detect(pending_tuple[1])
        shotDetector.save_results(pending_tuple[0])
        
        print("Finst detect the shots of ", pending_tuple[1])
        print("Total %d frames, take %f sec"%(shotDetector.frame_num, time.time()-st))
        del shotDetector

    except Exception as e:
        print(e)


def feature_procs(pending_tuple):
    s = time.time()
    print("[INFO] Extracting :", pending_tuple[0])

    try:
        vid_name = pending_tuple[0].split('/')[-1]
        result = DBclient.query("SELECT * FROM shot_list where \"name\"=\'"+vid_name+"\'")

        shot_list = ast.literal_eval(list(result.get_points(measurement='shot_list'))[0]['list'])

        color_entropy = mp.Value('d', 0.0); edge_entropy = mp.Value('d', 0.0); 
        conv_entropy = mp.Value('d', 0.0); temp_entropy = mp.Value('d', 0.0)

        color_proc = mp.Process(target=get_color_entropy, args=(pending_tuple[1], shot_list, color_entropy,))
        edge_proc = mp.Process(target=get_edge_entropy, args=(pending_tuple[1], shot_list, edge_entropy,))
        conv_proc = mp.Process(target=get_conv_entropy, args=(pending_tuple[1], shot_list, conv_entropy,))
        temp_proc = mp.Process(target=get_temp_conv_entropy, args=(pending_tuple[1], shot_list, temp_entropy,))
        color_proc.start(); 
        edge_proc.start(); 
        conv_proc.start(); 
        temp_proc.start()

        color_proc.join(); 
        edge_proc.join(); 
        conv_proc.join(); 
        temp_proc.join()


        print("color: %f, edge: %f, conv: %f, temp: %f"%(color_entropy.value, edge_entropy.value, conv_entropy.value, temp_entropy.value))
        json_body = [
                    {
                        "measurement": "visual_features_entropy_unnormalized",
                        "tags": {
                            "name": str(vid_name)
                        },
                        "fields": {
                            "color": float(color_entropy.value),
                            "edge": float(edge_entropy.value),
                            "conv": float(conv_entropy.value),
                            "temp": float(temp_entropy.value)
                        }
                    }
                ]
        DBclient.write_points(json_body)
        
    except Exception as e:
        print(e)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    # finally:
    #     color_proc.close() 
    #     edge_proc.close() 
    #     conv_proc.close()
    #     temp_proc.close()



if __name__=="__main__":
    # mp.set_start_method('spawn') # This is important for multiprocessing CUDA and should be here

    feature_pending_list = [] # (input_path, back_path)
    month = 11
    for day in range(23, 25):
        if month<=0:
            month = "0" + str(month)
        if day<=9:
            day = "0" + str(day)
        input_dir = "storage_server_volume/SmartPole/Pole1/2020-"+str(month)+"-"+str(day)+"_00-00-00"
        # input_dir = "/home/min/SmartPole/Pole1/2020-"+str(month)+"-"+str(day)+"_00-00-00"

        v_li = os.listdir(input_dir)
        v_li = sorted(v_li, key= lambda x: x)
        for v in v_li:
            input_path = os.path.join(input_dir, v)
            output_dir = os.path.join(input_dir,"background")
            if not os.path.isfile(input_path):
                continue
            if not os.path.isdir(os.path.join(input_dir,"background")):
                os.mkdir(os.path.join(input_dir,"background"))

            back_path = os.path.join(output_dir,"background_"+v)
            
            feature_pending_list.append((input_path, back_path)) 

    # if the video already be background subtraction, comment the code segment
    # for pending_tuple in feature_pending_list:
    #     background_subtraction(pending_tuple)
    # print("Background Subtraction Completed")


    # print("total %d videos"%(len(feature_pending_list)))
    # with Pool(12) as p:
    #     p.map(launch_shot_detector, feature_pending_list)
    #     print("Shot Detection Completed")
    for pending_tuple in feature_pending_list:
        feature_procs(pending_tuple)

    print("Feature Extraction Completed")



