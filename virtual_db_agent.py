from multiprocessing.connection import Client,Listener
from util.SetInterval import setInterval
# from optimal_downsampling_manager.resource_predictor.table_estimator import get_context,IATable,drop_measurement_if_exist

from influxdb import InfluxDBClient
from pathlib import Path
import datetime
import threading
import time
import os
import csv
import copy
import yaml

with open('configuration_manager/config.yaml','r') as yamlfile:
    data = yaml.load(yamlfile,Loader=yaml.FullLoader)

class DB_agent(object):
    def __init__(self):
        self.pending_list = list()
        self.DBclient = InfluxDBClient(host=data['global']['database_ip'], port=data['global']['port'], database=data['global']['database_name'], username='root', password='root')


        self.conn_send2DDM = None
        self.conn_listen2DP = None
        self.ready = threading.Event()
        self.lock=threading.Lock()
        

        self.DDM_size_threshold = 5*1024
        self.DDMflag = 0
        self.DDM_pending_videos = []
        self.storage_dir = "./storage_server_volume"


    def open_DDM_sending_port(self):
        while True:
            time.sleep(1)
            try:
                if self.conn_send2DDM is None:
                    address = ('localhost',int(data['global']['agent2DDM']))
                    self.conn_send2DDM = Client(address)
                    print("[INFO] Connected with DDM...")
            except Exception as e:
                print("Not detecting DDM, reconnecting...")


        ## this port is for simulation
    def open_DP_listening_port(self):
        address = ('localhost', int(data['global']['DP2agent']))
        listener = Listener(address)
        while True:
            time.sleep(1)
            try:
                if self.conn_listen2DP is None:
                    print("[INFO] Listening from Downsampling Platform")
                    self.conn_listen2DP = listener.accept()
                    print('connection accepted from', listener.last_accepted)

            except Exception as e:
                print("[INFO] Close listening port")
                self.conn_listen2DP.close()  
                self.conn_listen2DP = None  
                print(e)

    @setInterval(1)
    def check_ready(self):
        try:
            DDM_ready = self.conn_send2DDM
            DP_ready = self.conn_listen2DP
            if DDM_ready and DP_ready:
                self.ready.set()
        except Exception as e:
            print(e)

    #set port, run monitor    
    def run(self):
        self.ready.wait() #wait every port set up

        print("[INFO] Agent is running the task")
        try:
            self.do()
            input("Press any key to stop...")
            print()
        except Exception as e:    
            print(e)


    # @setInterval(trigger_interval*3600)
    def do(self):
        while True:
            self.DDM_gen_workload()
            print("Listening from DP & Waiting for generating the next batch of video...")
            finish = self.conn_listen2DP.recv()

            # if self.DDMflag ==len(self.DDM_pending_videos)-1:
            #     break
            break

        print("Evaluation finish!!!")
    


    def DDM_gen_workload(self):
        self.move_video_to_server()
        try:
            self.lock.acquire()
            print("Generate new pending list...")

            json_body = []
            for i in range(10,16):
                result = self.DBclient.query("select * from raw_11_"+str(i)) 

            # for r in self.DDM_pending_videos[self.DDMflag:]:
                # clip_date = int(r['name'].split("/")[-2].split("_")[-1])

                # if self.DDMflag == len(self.DDM_pending_videos)-1:
                #     print("Already look all video!!!")
                #     self.lock.release()
                #     return
                # else:
                #     self.DDMflag +=1
                

                # # log every hour
                # # self.log_database(clip_date, clip_hour)


                # ## if the video is new coming, mkdir and mv it to stored folder
                # clip_path = r['name'].split("/")
                # new_path = os.path.join(self.storage_dir,clip_path[-2])
                # if not os.path.isdir(new_path):
                #     os.mkdir(new_path) 
                # stored_clip_name = os.path.join(new_path,clip_path[-1])
                # if not os.path.isfile(stored_clip_name):
                #     cmd = "cp %s %s"%(r['name'], stored_clip_name)
                #     os.system(cmd)
                

                # Save and log the new videos in the database
                for c in list(result.get_points(measurement="raw_11_"+str(i))):
                    raw_size = os.path.getsize(c['name']) / pow(2,20)
                    parse =  c['name'].split('/')[-1].split('_')
                    date = parse[-2].split("-")
                    hour = int(parse[-1].split("-")[0])
                    
                    json_body.append(
                        {
                            "measurement": "pending_video",
                            "tags": {
                                "month": int(date[1]),
                                "day": int(date[2]),
                                "hour": int(hour),
                                "prev_fps":int(24),
                                "prev_bitrate":int(1000),
                                "fps": int(1),
                                "bitrate": int(10),
                                "a_para_illegal_parking": int(1),
                                "a_para_people_counting": int(1),
                                
                            },
                            "fields": {
                                "name": str(c['name']),
                                "raw_size":float(raw_size)
                            }
                        }
                    )
                    
            self.DBclient.write_points(json_body, database='storage', time_precision='ms', batch_size=1000, protocol='json')
            
                # sumsize = sum(f.stat().st_size for f in Path(self.storage_dir).glob('**/*') if f.is_file())
                # sumsize = sumsize/pow(2,20)
                # if sumsize > self.DDM_size_threshold:
                #     print(sumsize,self.DDM_size_threshold)
                #     print("Out of size at %s, trigger prob2..."%(r['name']))
                #     break

                ## Get the pending video for downsampling from databases 'stored_month_day'


            
            self.lock.release()
            self.conn_send2DDM.send(True)
>>>>>>> 42cc2248a98fa67668ca59a4e89187610d06e7f5
            print("Send signal to DDM")
        except Exception as e:
            print(e)


    def move_video_to_server(self):
        json_body = []
        for i in range(4,5):
            result = self.DBclient.query("SELECT * FROM raw_11_"+str(i))
            result_list = list(result.get_points(measurement="raw_11_"+str(i)))
            for r in result_list:
                raw_size = os.path.getsize(r['name']) / pow(2,20)
                json_body.append({
                    "measurement": "videos_in_server",
                    "tags": {
                        "name": str(r['name']),
                        "host": "webcamPole1"
                    },
                    "fields": {
                        "fps":float(24.0),
                        "bitrate":float(1000.0),
                        "prev_fps":float(24.0),
                        "prev_bitrate":float(1000.0),
                        "a_para_illegal_parking": float(1),
                        "a_para_people_counting": float(1),
                        "raw_size":float(raw_size)
                    }
                }
            )
        self.DBclient.write_points(json_body, database='storage', time_precision='ms', batch_size=1000, protocol='json')

        # for r in self.DDM_pending_videos[self.DDMflag:]:
            # clip_date = int(r['name'].split("/")[-2].split("_")[-1])

            # if self.DDMflag == len(self.DDM_pending_videos)-1:
            #     print("Already look all video!!!")
            #     self.lock.release()
            #     return
            # else:
            #     self.DDMflag +=1
            

            # # log every hour
            # # self.log_database(clip_date, clip_hour)


            # ## if the video is new coming, mkdir and mv it to stored folder
            # clip_path = r['name'].split("/")
            # new_path = os.path.join(self.storage_dir,clip_path[-2])
            # if not os.path.isdir(new_path):
            #     os.mkdir(new_path) 
            # stored_clip_name = os.path.join(new_path,clip_path[-1])
            # if not os.path.isfile(stored_clip_name):
            #     cmd = "cp %s %s"%(r['name'], stored_clip_name)
            #     os.system(cmd)
            

            # raw_size = os.path.getsize(stored_clip_name) / pow(2,20)
            
            # ???? what is this ??? maybe to ensure the least video size
            # if raw_size<=0:
            #     raw_size = 6

            ## Save and log the new videos in the database
            # json_body = [
            #     {
            #         "measurement": "",
            #         "tags": {
            #             "name": str(clip_name),
            #             "fps":float(24.0),
            #             "bitrate":float(1000.0),
            #             "host": "webcamPole1"
            #         },
            #         "fields": {
            #             "a_parameter_0": float(r['a_para_illegal_parking']),
            #             "a_parameter_1": float(r['a_para_people_counting']),
            #             "raw_size":float(raw_size)
            #         }
            #     }
            # ]
            # self.DBclient.write_points(json_body)
            

            # sumsize = sum(f.stat().st_size for f in Path(self.storage_dir).glob('**/*') if f.is_file())
            # sumsize = sumsize/pow(2,20)
            # if sumsize > self.DDM_size_threshold:
            #     print(sumsize,self.DDM_size_threshold)
            #     print("Out of size at %s, trigger prob2..."%(r['name']))
            #     break