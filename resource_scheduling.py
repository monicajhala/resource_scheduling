from pyomo.environ import *
from pyomo.opt import SolverFactory
from pymongo import MongoClient
import pandas as pd 
import gekko as GEKKO

from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import json
# from algo import *

def upload_mongo(data, plan_name, project_name, employee,fname="sample.csv", dept=""):

    client = MongoClient("mongodb://dbownpi:PiowSr18@185.105.4.52:27017/monkviz_1478_dev",connect=False)
    mydb = client['monkviz_1478_dev']
    mycol = mydb['schedule_Data']

    records = []
    temp = []
    # dummy_rec = {'morning': [], 'evening': [], 'night': []}
    # for dts_ in hdts:
    #     week_table[dts_] = dummy_rec
    for wk in workers_needed:
        rec= {}
        # print(wk)
        for day, day_dt in week_table.items():
            tmp= {}
            rec= {}
            # print("w - {} | day - {}".format(wk, day))
            for shift, shift_details in day_dt.items():
                if wk in shift_details:
                    tmp["name"] = int(wk)
                    tmp["dept"] = dept
                    # tmp["day"] = day
                    tmp["date"] = day
                    tmp["shift"] = shift
                    tmp["empid"] = wk
                    tmp["employee_name"] = employee[wk]
                    # tmp["plan"] = plan_name
                    tmp["task"] = plan_name
                    tmp["project"] = project_name

                    if shift == 'morning':
                        tmp["color"] = "colorSet.getIndex(3).brighten(1.2)"
                    elif shift == 'evening':
                        tmp["color"] = "colorSet.getIndex(6).brighten(1.2)"
                    else:
                        tmp["color"] = "colorSet.getIndex(4).brighten(1)"
                        # tmp["color"] = "black"

                    #----------------- convert next day -----------
                    from datetime import datetime,date, timedelta
                    date_str = day
                    formatter_string = "%Y-%m-%d" 
                    datetime_object = datetime.strptime(date_str, formatter_string)
                    date_object = datetime_object.date()
                    next_day = date_object + timedelta(days=1)
                    tmp["toDate"] = str(next_day).split()[0]
                    tmp["fromDate"] = day
                    #---------- custom records---
                    tmp["start_time"] = day
                    if shift == "morning":
                        tmp["start_time"] = "6 AM"
                        tmp["end_time"] = "2 PM"
                    elif shift == "evening":
                        tmp["start_time"] = "2 PM"
                        tmp["end_time"] = "10 PM"
                    else:
                        tmp["start_time"] = "10 PM"
                        tmp["end_time"] = "6 AM"



                    temp.append(tmp)
                    # print(temp)


    emp_shift_count = {}
    emp_track = {}
    for rr in temp:
        emp_track[rr['empid']] = 0

    for rr in temp:
        emp_track[rr["empid"]] += 1

    print(emp_track)
    out_df = pd.DataFrame.from_dict(temp)
    final_df = out_df[["empid","date","employee_name","shift","project","task","start_time","end_time"]]
    final_df.to_csv("planned/{}".format(fname), index=False)
    for i in temp:
        try:
            print(i)
            mycol.insert(i)
        except:
            print("except")

class Planning(object):
    
    def __init__(self, worker_list=["W1","W2","W3","W4"], shift=['morning', 'evening', 'night'], emp_req=10, timeline=14,start_date=None,end_date=None, cmb_=None):
        if start_date == None:
            self.days = []
        else:
            from dateutil import rrule, parser
            date1 = start_date
            date2 = end_date

            dates = list(rrule.rrule(rrule.DAILY,dtstart=parser.parse(date1),until=parser.parse(date2)))
            holiday_dates = []
            for dd in dates:
                if dd.weekday() == 4:
                    holiday_dates.append(dd)

            dates = [str(dt).split()[0] for dt in dates if dt not in holiday_dates]
            holiday_dates = [str(dt).split()[0] for dt in holiday_dates]
            print(dates)
            print("HL : ",holiday_dates)
            print("No of days : {}".format(len(dates)))
            print("Total : {}".format(emp_req))
            self.days = dates
        self.shifts = shift
        self.days_shifts = {day: self.shifts for day in self.days}
        self.workers = worker_list[:int(emp_req)]
        print(self.workers)
        self.model = ConcreteModel()
        # binary variables representing if a worker is scheduled somewhere
        self.model.works = Var(((worker, day, shift) for worker in self.workers for day in self.days for shift in self.days_shifts[day]),
                          within=Binary, initialize=0)

        # binary variables representing if a worker is necessary
        self.model.needed = Var(self.workers, within=Binary, initialize=0)

        # binary variables representing if a worker worked on sunday but not on saturday (avoid if possible)
        self.model.no_pref = Var(self.workers, within=Binary, initialize=0)
        print("[INFO] Model Binaries --------------")
        # add objective function to the model. rule (pass function) or expr (pass expression directly)
        self.model.obj = Objective(rule=self.obj_rule, sense=minimize)



        self.model.constraints = ConstraintList()  # Create a set of constraints
        print("[INFO] Model Constraint --------------")
        # Constraint: all shifts are assigned
        if cmb_ == None:
            if (emp_req//2) > 4:
                for day in self.days:
                    for shift in self.days_shifts[day]:
                        if day in self.days[:] and shift in ['morning']:
                            # weekdays' and Saturdays' day shifts have exactly two workers
                            self.model.constraints.add(  # to add a constraint to model.constraints set
                                (emp_req//3) == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira
                            )
                        elif day in self.days[:] and shift in ['evening']:
                            # weekdays' and Saturdays' day shifts have exactly two workers
                            self.model.constraints.add(  # to add a constraint to model.constraints set
                                (emp_req//3) == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira
                            )
                        else:
                            # Sundays' and nights' shifts have exactly one worker
                            self.model.constraints.add(
                                (emp_req//3)-1 == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira
                            )

            # elif (emp_req//2) >=2 and (emp_req//2) <= 4:
            #     for day in self.days:
            #         for shift in self.days_shifts[day]:
            #             if day in self.days[:-1] and shift in ['morning']:
            #                 # weekdays' and Saturdays' day shifts have exactly two workers
            #                 self.model.constraints.add(  # to add a constraint to model.constraints set
            #                     (emp_req//2)-1 == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira
            #                 )
            #             else:
            #                 # Sundays' and nights' shifts have exactly one worker
            #                 self.model.constraints.add(
            #                     (emp_req//2)-1 == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira
            #                 )

            # else:
            #     for day in self.days:
            #         for shift in self.days_shifts[day]:
            #             if day in self.days[:-1] and shift in ['morning']:
            #                 # weekdays' and Saturdays' day shifts have exactly two workers
            #                 self.model.constraints.add(  # to add a constraint to model.constraints set
            #                     emp_req-1 == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira
            #                 )
            #             else:
            #                 # Sundays' and nights' shifts have exactly one worker
            #                 self.model.constraints.add(
            #                     1 == sum(self.model.works[worker, day, shift] for worker in self.workers) #--- dynamic ratio -hambira 
            #                 )
        else:
            ms, es, ns = int(cmb_[0]),int(cmb_[1]),int(cmb_[2])
            print("---->>>>> {} {} {}".format(ms, es, ns))
            print("---->>>>> {} {} {}".format(type(ms), es, ns))
            #---------------------------
            for day in self.days:
                for shift in self.days_shifts[day]:
                    if day in self.days[:] and shift in ['morning']:
                        # weekdays' and Saturdays' day shifts have exactly two workers
                        self.model.constraints.add(  # to add a constraint to model.constraints set
                            int(ms) == sum(self.model.works[worker, day, shift] for worker in self.workers[:5])
                        )
                    elif day in self.days[:] and shift in ['evening']:
                        # weekdays' and Saturdays' day shifts have exactly two workers
                        self.model.constraints.add(  # to add a constraint to model.constraints set
                            int(es) == sum(self.model.works[worker, day, shift] for worker in self.workers[5:8]) #--- dynamic ratio -hambira
                        )
                    else:
                        # Sundays' and nights' shifts have exactly one worker
                        self.model.constraints.add(
                            int(ns) == sum(self.model.works[worker, day, "night"] for worker in self.workers[8:]) #--- dynamic ratio -hambira
                        )

                            

        # Constraint: no more than 40 hours worked
        if len(dates) > 7 and emp_req > 7:
            print("-------------->>>>>> Condiion 1")
            for worker in self.workers:
                self.model.constraints.add(
                    (len(dates)*8) >= sum(8 * self.model.works[worker, day, shift] for day in self.days for shift in self.days_shifts[day])
                )
        else:
            print("-------------->>>>>>  Condiion 3")

            for worker in self.workers:
                self.model.constraints.add(
                    (len(dates)*8) >= sum(8 * self.model.works[worker, day, shift] for day in self.days for shift in self.days_shifts[day])
                )
        # elif len(dates) > 7 and emp_req < 7:
        #     print("-------------->>>> Start- date ------- ")
        #     print("-------------->>>>>> Condiion 2")

        #     for worker in self.workers:
        #         self.model.constraints.add(
        #             88 >= sum(8 * self.model.works[worker, day, shift] for day in self.days for shift in self.days_shifts[day])
        #         )
        # else:
        #     print("-------------->>>>>>  Condiion 3")

        #     for worker in self.workers:
        #         self.model.constraints.add(
        #             (len(dates)*8) >= sum(8 * self.model.works[worker, day, shift] for day in self.days for shift in self.days_shifts[day])
        #         )

       
        # Constraint: rest between two shifts is of 12 hours (i.e., at least two shifts)
        for worker in self.workers:
            for j in range(len(self.days)):
                try:
                    # if working in morning, cannot work again that day
                    # self.model.constraints.add(
                    #     1 >= sum(self.model.works[worker, self.days[j], shift] for shift in self.days_shifts[self.days[j]]) #+ self.model.works[worker, self.days[(j + 1) % len(self.days)], 'morning']
                    # )
                    # if working in morning, cannot work again that day
                    self.model.constraints.add(
                        1 >= sum(self.model.works[worker, self.days[j], shift] for shift in ['morning', 'night']) +
                        self.model.works[worker, self.days[(j + 1) % 7], 'evening']
                    )
                    # if working in evening, until next evening (note that after sunday comes next monday)
                    self.model.constraints.add(
                        1 >= sum(self.model.works[worker, self.days[j], shift] for shift in ['evening', 'night']) +
                        self.model.works[worker, self.days[(j + 1) % 7], 'morning']
                    )
                    # # if working in night, until next night
                    self.model.constraints.add(
                        1 >= self.model.works[worker, self.days[j], 'night'] +
                        sum(self.model.works[worker, self.days[(j + 1) % 7], shift] for shift in ['morning', 'evening'])
                    )   
                except Exception as e:
                    print("Exception : {}".format(e))
                # # if working in evening, until next evening (note that after Sunday comes next monday)
                # self.model.constraints.add(
                #     1 >= sum(self.model.works[worker, self.days[j], shift] for shift in ['evening','night']) +
                #     self.model.works[worker, self.days[(j + 1) % len(dates)], 'morning']
                # )
                # # if working in night, until next night
                # self.model.constraints.add(
                #     1 >= self.model.works[worker, self.days[j], 'night'] +
                #     sum(self.model.works[worker, self.days[(j + 1) % 7], shift] for shift in ['morning','evening'])
                # )

        # Constraint (def of model.needed)
        for worker in self.workers:
            self.model.constraints.add(
                10000 * self.model.needed[worker] >= sum(self.model.works[worker, day, shift] for day in self.days for shift in self.days_shifts[day])
            )  # if any model.works[worker, ·, ·] non-zero, model.needed[worker] must be one; else is zero to reduce the obj function
            # 10000 is to remark, but 5 was enough since max of 40 hours yields max of 5 shifts, the maximum possible sum

        # Constraint (def of model.no_pref)
        # for worker in self.workers:
        #     print("[INFO] Setting no_pref for {}".format(worker))
        #     self.model.constraints.add(
        #         self.model.no_pref[worker] >= sum(self.model.works[worker, 'Sat', shift] for shift in self.days_shifts['Sat'])
        #         - sum(self.model.works[worker, '2019-09-06', shift] for shift in self.days_shifts['2019-09-06'])
        #     )  # if not working on sunday but working saturday model.needed must be 1; else will be zero to reduce the obj function

        #     self.model.constraints.add(
        #         self.model.no_pref[worker] >= sum(self.model.works[worker, 'Sat', shift] for shift in self.days_shifts['Sat'])
        #         - sum(self.model.works[worker, '2019-09-06', shift] for shift in self.days_shifts['2019-09-06'])
            # )  # if not working on sunday but working saturday model.needed must be 1; else will be zero to reduce the obj function
        #     self.model.constraints.add(
        #         self.model.no_pref[worker] >= sum(self.model.works[worker, 'Sat1', shift] for shift in self.days_shifts['Sat1'])
        #         - sum(self.model.works[worker, 'Sun1', shift] for shift in self.days_shifts['Sun1'])
        #     ) # if not working on sunday but working saturday model.needed must be 1; else will be zero to reduce the obj function
        #     # self.model.constraints.add(
        #     #     self.model.no_pref[worker] >= sum(self.model.works[worker, 'Sat2', shift] for shift in self.days_shifts['Sat2'])
        #     #     - sum(self.model.works[worker, 'Sun2', shift] for shift in self.days_shifts['Sun2'])
        #     # ) 
    
    #--------------------------------------------------------------------------
    def run_algorithm(self):
        opt = SolverFactory('cbc')  # choose a solver
        results = opt.solve(self.model)  # solve the model with the selected solver
        return self.model

    def get_workers_needed(self, needed):
        """Extract to a list the needed workers for the optimal solution."""
        workers_needed = []
        for worker in self.workers:
            if needed[worker].value == 1:
                workers_needed.append(worker)
        return workers_needed


    def get_work_table(self, works):
        """Build a timetable of the week as a dictionary from the model's optimal solution."""
        week_table = {day: {shift: [] for shift in self.days_shifts[day]} for day in self.days}
        for worker in self.workers:
            for day in self.days:
                for shift in self.days_shifts[day]:
                        if works[worker, day, shift].value == 1:
                            week_table[day][shift].append(worker)
        return week_table


    def get_no_preference(self, no_pref):
        """Extract to a list the workers not satisfied with their weekend preference."""
        return [worker for worker in self.workers if no_pref[worker].value == 1]

    
    # Define an objective function with model as input, to pass later
    def obj_rule(self, m):
        c = len(self.workers)
        return sum(m.no_pref[worker] for worker in self.workers) + sum(c * m.needed[worker] for worker in self.workers)
    # we multiply the second term by a constant to make sure that it is the primary objective
    # since sum(m.no_prefer) is at most len(workers), len(workers) + 1 is a valid constant.


class DialogueServer(BaseHTTPRequestHandler):

    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):

        logging.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
        self._set_response()
        self.wfile.write("GET request for {}".format(self.path).encode('utf-8'))

    def do_POST(self):
        print(self.headers)
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        p_data = post_data.decode('utf-8')
        data = json.loads(p_data)
        # print(data)
        
        plans = pd.read_excel("planner.xlsx")
        used_emp = []
        for ix, pl in plans.iterrows():
            # print(pl)
            print(pl["task"])
            emp = pd.read_excel("emp.xlsx")
            skill_req = pl["skill"]
            # skill_req = str(input("Enter Skill : "))
            filtered_emp = list(emp[emp["Skill"] == skill_req]["Id No"].astype('str'))
            filtered_emp_name = list(emp[emp["Skill"] == skill_req]["Name"].astype('str'))
            employee_base = dict(zip(filtered_emp,filtered_emp_name))
            prj_name = pl["project"]
            total_emp_req = pl["resource_required"]
            filtered_emp = [emm for emm in filtered_emp if emm not in used_emp]
            filtered_emp = filtered_emp[:total_emp_req+1]
            depttt = pl["dept"]
            # for emp_req , emp_dates in plan.items():
                # try:
            st_date = pl['start_date']
            ed_date = pl['end_date']
            plan_name = pl["task"]
            try:
                cmb = pl['cmb'].split(",")
            except:
                cmb = None
            print("\n\n-------------------- PLAN {} --------------------- \n".format(st_date))

            ML = Planning(worker_list=filtered_emp, emp_req=int(total_emp_req), start_date=st_date, end_date=ed_date, cmb_=cmb)
            model = ML.run_algorithm()
            workers_needed = ML.get_workers_needed(model.needed)  # dict with the optimal timetable
            week_table = ML.get_work_table(model.works)  # list with the required workers
            workers_no_pref = ML.get_no_preference(model.no_pref)  # list with the non-satisfied workers (work on Sat but not on Sun)
            filtered_emp = [itm for itm in filtered_emp if itm not in workers_needed] #---->> new filtered data 
            import json
            # with open('task_{}_{}.json'.format(st_date,emp_req), 'w') as fp:
            #     json.dump(week_table, fp)

            #------------- summary ------------
            import pprint
            # pprint.pprint(week_table)

            print("\n")
            print("[INFO] workers selected : {}".format(workers_needed))
            print("[INFO] workers not selected : {}".format(workers_no_pref))
            for em in workers_needed:
                used_emp.append(em)
            upload_mongo(workers_needed,plan_name,prj_name,employee_base,fname="final_{}_{}.csv".format(plan_name,st_date),dept=depttt)
        import os
        dfs = [pd.read_csv(os.path.join('planned',x)) for x in os.listdir("planned") if os.path.isfile(os.path.join("planned",x))]
        dffs = pd.concat(dfs)
        dffs.to_csv("final_schedule.csv", index=False)
        #---------- ALGO --------------


        #-----------------------------

        self._set_response()
        self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=DialogueServer, host='127.0.0.1',port='8080'):
    logging.basicConfig(level=logging.INFO)
    server_address = (host, port)
    httpd = server_class(server_address, handler_class)
    logging.info('Starting RPA Server...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')


if __name__ == '__main__':
    # run(host = '108.160.137.155',port=int('8080'))
    
    # =============================================================================
    plans = pd.read_excel("nurse_pln.xlsx")
    used_emp = []
    for ix, pl in plans.iterrows():
        # print(pl)
        print(pl["task"])
        emp = pd.read_excel("nurse.xlsx")
        skill_req = pl["skill"]
        # skill_req = str(input("Enter Skill : "))
        filtered_emp = list(emp[emp["Skill"] == skill_req]["Emp_ID"].astype('str'))
        filtered_emp_name = list(emp[emp["Skill"] == skill_req]["Emp_name"].astype('str'))
        employee_base = dict(zip(filtered_emp,filtered_emp_name))
        prj_name = pl["project"]

        # for ids__, name__ in zip(filtered_emp,filtered_emp_name):

        total_emp_req = pl["resource_required"]
        filtered_emp = [emm for emm in filtered_emp if emm not in used_emp]
        filtered_emp = filtered_emp[:total_emp_req+1]
        depttt = pl["dept"]
        print(filtered_emp)
        # for emp_req , emp_dates in plan.items():
            # try:
        st_date = pl['start_date']
        ed_date = pl['end_date']
        plan_name = pl["task"]
        try:
            cmb = pl['cmb'].split(",")
        except:
            cmb = None
        print("\n\n-------------------- PLAN {} --------------------- \n".format(st_date))

        ML = Planning(worker_list=filtered_emp, emp_req=int(total_emp_req), start_date=st_date, end_date=ed_date, cmb_=cmb)
        model = ML.run_algorithm()
        workers_needed = ML.get_workers_needed(model.needed)  # dict with the optimal timetable
        week_table = ML.get_work_table(model.works)  # list with the required workers
        workers_no_pref = ML.get_no_preference(model.no_pref)  # list with the non-satisfied workers (work on Sat but not on Sun)
        filtered_emp = [itm for itm in filtered_emp if itm not in workers_needed] #---->> new filtered data 
        import json
        # with open('task_{}_{}.json'.format(st_date,emp_req), 'w') as fp:
        #     json.dump(week_table, fp)


        #------------- summary ------------
        import pprint
        pprint.pprint(week_table)

        # for o in range(0,len(ML.days), 6):
        #     temp_days = ML.days[o:o+6]
        #     # temp_days
        #     print("------>>",temp_days)
        #     for dy in temp_days:
        #         mn = week_table[dy]["morning"]
        #         ev = week_table[dy]["evening"]
        #         nt = week_table[dy]["night"]
        #         week_table[dy]["morning"] = nt
        #         week_table[dy]["evening"] = mn
        #         week_table[dy]["night"] = ev

        o=6
        temp_days = ML.days[o:o+6]
        # temp_days
        print("------>>",temp_days)
        for dy in temp_days:
            mn = week_table[dy]["morning"]
            ev = week_table[dy]["evening"]
            nt = week_table[dy]["night"]
            week_table[dy]["morning"] = nt
            week_table[dy]["evening"] = mn
            week_table[dy]["night"] = ev

        temp_days = ML.days[o+6:o+12]
        # temp_days
        print("------>>",temp_days)
        for dy in temp_days:
            mn = week_table[dy]["morning"]
            ev = week_table[dy]["evening"]
            nt = week_table[dy]["night"]
            week_table[dy]["morning"] = ev
            week_table[dy]["evening"] = nt
            week_table[dy]["night"] = mn


        print("\n")
        print("[INFO] workers selected : {}".format(workers_needed))
        print("[INFO] workers not selected : {}".format(workers_no_pref))
        for em in workers_needed:
            used_emp.append(em)
        upload_mongo(workers_needed,plan_name,prj_name,employee_base,fname="final_{}_{}.csv".format(plan_name,st_date),dept=depttt)

    import os
    dfs = [pd.read_csv(os.path.join('planned',x)) for x in os.listdir("planned") if os.path.isfile(os.path.join("planned",x))]
    dffs = pd.concat(dfs)
    dffs.to_csv("final_schedule.csv", index=False)