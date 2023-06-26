import csv
import json
import logging
import os
import random
import string
import sys
import time
from datetime import datetime
from random import randint

import uuid
import logging

import locust
import numpy as np
from locust import events
from locust.runners import MasterRunner
from locust import task, constant, HttpUser, User, TaskSet
from locust import LoadTestShape
from locust.env import Environment
from requests.adapters import HTTPAdapter
from test_data import USER_CREDETIALS, TRIP_DATA, TRAVEL_DATES

locust.stats.PERCENTILES_TO_REPORT = [0.25, 0.50, 0.75, 0.80, 0.90, 0.95, 0.98, 0.99, 0.999, 0.9999, 1.0]
VERBOSE_LOGGING = 0  # ${LOCUST_VERBOSE_LOGGING}
# stat_file = open("output/requests_stats_u50_5.csv", "w")
LOG_STATISTICS_IN_HALF_MINUTE_CHUNKS = False
RETRY_ON_ERROR = True
MAX_RETRIES = 100

state_data = []
user_count = 0
stage_duration = 0
stage_duration_passed = 0
stage_users = 0
stage_rate = 0
adminToken = 0;
userList = [];

max_experiment_duration = 86400 #in seconds. This is to guarantee users will spawn only once during the test duration

STATUS_BOOKED = 0
STATUS_PAID = 1
STATUS_COLLECTED = 2
STATUS_CANCELLED = 4
STATUS_EXECUTED = 6

spawning_complete = False
@events.spawning_complete.add_listener
def on_spawning_complete(user_count, **kwargs):
    global spawning_complete
    spawning_complete = True
    
def get_json_from_response(response):
    response_as_text = response.content.decode('UTF-8')
    response_as_json = json.loads(response_as_text)
    return response_as_json

def try_until_success(f,retries=MAX_RETRIES):
    for attempt in range(retries):   
        logging.debug(f"Calling function {f.__name__}, attempt {attempt}...")
        
        try:
            result, status = f()
            result_as_string = str(result)
            logging.debug(f"Result of calling function {f.__name__} was: {result_as_string}.")
            if status == 1:                
                return result
            else:
                logging.debug(f"Failed calling function {f.__name__}, response was {result_as_string}, trying again:")
                time.sleep(1)
        except Exception as e:
            exception_as_text = str(e)
            logging.debug(f"Failed calling function {f.__name__}, exception was: {exception_as_text}, trying again.")
            time.sleep(1)

        if not RETRY_ON_ERROR:
            break
        
    raise Exception("Weird... Cannot call endpoint.") 

def random_string_generator():
    len = random.randint(8, 16)
    prob = random.randint(0, 100)
    if prob < 25:
        random_string = ''.join([random.choice(string.ascii_letters) for n in range(len)])
    elif prob < 50:
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(len)])
    elif prob < 75:
        random_string = ''.join(
            [random.choice(string.ascii_letters + string.digits + string.punctuation) for n in range(len)])
    else:
        random_string = ''
    return random_string


def random_date_generator():
    temp = random.randint(0, 4)
    random_y = 2000 + temp * 10 + random.randint(0, 9)
    random_m = random.randint(1, 12)
    random_d = random.randint(1, 31)  # assumendo che la data possa essere non sensata (e.g. 30 Febbraio)
    return str(random_y) + '-' + str(random_m) + '-' + str(random_d)


def postfix(expected=True):
    if expected:
        return '_expected'
    return '_unexpected'

def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days_ahead)

def get_name_suffix(name):
    global spawning_complete
    if not spawning_complete:
        name = name + "_spawning"

    if LOG_STATISTICS_IN_HALF_MINUTE_CHUNKS:
        now = datetime.now()
        now = datetime(now.year, now.month, now.day, now.hour, now.minute, 0 if now.second < 30 else 30, 0)
        now_as_timestamp = int(now.timestamp())
        return f"{name}@{now_as_timestamp}"
    else:
        return name

def execute_load():
    _conn = create_conn(conn_string)
    rs = _conn.execute(query)
    return rs

class Requests:

    def __init__(self, client):
        self.client = client
        dir_path = os.path.dirname(os.path.realpath(__file__))
        handler = logging.FileHandler(os.path.join(dir_path, "locustfile_debug.log"))
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        user = random.choice(USER_CREDETIALS)
        self.user_name = user
        self.password = user
        self.trip_detail = random.choice(TRIP_DATA)
        self.food_detail = {}
        self.departure_date = random.choice(TRAVEL_DATES)
        self.user_name = "fdse_microservice"
        self.password = "111111"
        self.bearer = ""
        self.user_id = 0
        self.contactid = 0
        
        if VERBOSE_LOGGING == 1:
            logger = logging.getLogger("Debugging logger")
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            self.debugging_logger = logger
        else:
            self.debugging_logger = None

    def log_verbose(self, to_log):
        if self.debugging_logger is not None:
            self.debugging_logger.debug(json.dumps(to_log))

    def home(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get('/index.html', name=req_label, catch_response=True) as response:
            if response.elapsed.total_seconds() > 0.01:
                #print("Home load fail response: " + str(response.elapsed.total_seconds()))
                response.failure("Time out on loading. Dropped query.")
                to_log = {'name': req_label, 'expected': 'time_out', 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
                self.log_verbose(to_log)
            else:
                #print("Home load response: " + str(response.elapsed.total_seconds()))
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
                self.log_verbose(to_log)

    def try_to_read_response_as_json(self, response):
        try:
            return response.json()
        except:
            try:
                return response.content.decode('utf-8')
            except:
                return response.content

    def search_ticket(self, expected):
        logging.debug("search ticket")
        stations = ["Shang Hai", "Tai Yuan", "Nan Jing", "Wu Xi", "Su Zhou", "Shang Hai Hong Qiao", "Bei Jing",
                    "Shi Jia Zhuang", "Xu Zhou", "Ji Nan", "Hang Zhou", "Jia Xing Nan", "Zhen Jiang"]
        from_station, to_station = random.sample(stations, 2)
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json"}
        body_start = {
            "startingPlace": from_station,
            "endPlace": to_station,
            "departureTime": departure_date
        }
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.post(
            url="/api/v1/travelservice/trips/left",
            headers=head,
            catch_response=True,
            json=body_start,
            name=req_label) as response:
            #print (response.json())
            if not response.json() or not response.json()["data"]:
                response = self.client.post(
                    url="/api/v1/travel2service/trips/left",
                    headers=head,
                    json=body_start,
                    name=req_label)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                    'response_time': time.time() - start_time,
                    'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    # def search_departure(self, expected):
    #     logging.info("search_departure")
    #     stations = ["Shang Hai", "Tai Yuan", "Nan Jing", "Wu Xi", "Su Zhou", "Shang Hai Hong Qiao", "Bei Jing",
    #                 "Shi Jia Zhuang", "Xu Zhou", "Ji Nan", "Hang Zhou", "Jia Xing Nan", "Zhen Jiang"]
    #     from_station, to_station = random.sample(stations, 2)
    #     if expected:
    #         self.search_ticket(date.today().strftime(random_date_generator()), from_station, to_station, expected)
    #     else:
    #         self.search_ticket(date.today().strftime(random_date_generator()), random_string_generator(), "Su Zhou",
    #                            expected)

    def _create_user(self, expected):

        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        document_num = random.randint(1, 5)  # added by me
        with self.client.post(url="/api/v1/adminuserservice/users",
                              headers={
                                  "Authorization": self.bearer, "Accept": "application/json",
                                  "Content-Type": "application/json"},
                              json={"documentNum": document_num, "documentType": 0, "email": "string", "gender": 0,
                                    "password": self.user_name, "userName": self.user_name},
                              name=req_label) as response2:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response2.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response2)}
            self.log_verbose(to_log)

    def _navigate_to_client_login(self, expected=True):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get('/client_login.html', name=req_label) as response:
            to_log = {'name': req_label, 'expected': True, 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
            self.log_verbose(to_log)

    def loginAdmin(self, expected):
        global adminToken
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()

        def api_call_admin_login():
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            body = {"username": "admin", "password": "222222"}
            response = self.client.post(url="/api/v1/users/login", headers=headers, json=body, name=get_name_suffix("admin_login"))
            response_as_json = get_json_from_response(response)
            return response_as_json, response_as_json["status"]

        print("Login as admin")
        response_as_json = try_until_success(api_call_admin_login)
        data = response_as_json["data"]
        adminToken = data["token"]

    def loginCreateUser(self, expected):
        global adminToken
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        user_name = str(uuid.uuid4())
        password = "12345678"
        start_time = time.time()

        def api_call_admin_create_user():
            headers = {"Authorization": f"Bearer {adminToken}", "Accept": "application/json", "Content-Type": "application/json"}
            body = {"documentNum": None, "documentType": 0, "email": "string", "gender": 0, "password": password, "userName": user_name}
            response = self.client.post(url="/api/v1/adminuserservice/users", headers=headers, json=body, name=get_name_suffix("admin_create_user"))
            response_as_json = get_json_from_response(response)
            return response_as_json, response_as_json["status"]
            
        print("Creating user "+user_name)
        response_as_json = try_until_success(api_call_admin_create_user)
        if response_as_json is not None:
            userList.append(user_name)
        
    def adminGetUsers(self, expected):
        global adminToken
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()

        def api_call_admin_get_users():
            headers = {"Authorization": f"Bearer {adminToken}", "Accept": "application/json", "Content-Type": "application/json"}
            response = self.client.get(url="/api/v1/adminuserservice/users", headers=headers, name=get_name_suffix("admin_get_users"))
            response_as_json = get_json_from_response(response)
            #print(response_as_json)
            return response_as_json, response_as_json["status"]
            
        print("Get all users...")
        response_as_json = try_until_success(api_call_admin_get_users)
        #print(response_as_json)
        if response_as_json is not None:
            print(response_as_json['data'])
            for userRecord in response_as_json['data']:
                userList.append(userRecord['userId'])
            print(userList)

    def login(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        user_name = random.choice(userList)
        password = "12345678"
        start_time = time.time()

        def api_call_login():
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            body = {"username": user_name, "password": password}
            response = self.client.post(url="/api/v1/users/login", headers=headers, json=body, name=get_name_suffix("login"))
            response_as_json = get_json_from_response(response)
            return response_as_json, response_as_json["status"]

        print("Loggin as user "+user_name)
        if (expected):
            response_as_json = try_until_success(api_call_login)
        else:
            password = "0000000" #Wrong password. Do not retry login, MAX_RETRIES override to 1.
            response_as_json = try_until_success(api_call_login,1)
            
        data = response_as_json["data"]
        user_id = data["userId"]
        token = data["token"]
        to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                'response_time': time.time() - start_time,
                'response': self.try_to_read_response_as_json(data)}
        self.log_verbose(to_log)
        
        if token is not None:
            self.bearer = "Bearer " + token
            self.user_id = user_name
            print("Login success " + user_name + " with token: " + str(token))
        else:
            print("Login failed " + user_name + " with error: " + data)
            
        #def api_call_create_contact_for_user():
        #    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
        #    body = {"name": user_name, "accountId": user_id, "documentType": "1", "documentNumber": "123456", "phoneNumber": "123456"}
        #    response = self.client.post(url="/api/v1/contactservice/contacts", headers=headers, json=body, name=get_name_suffix("admin_create_contact"))
        #    return response_as_json, response_as_json["status"]

        #try_until_success(api_call_create_contact_for_user)


        return user_id, token

    def loginOld(self, expected):
        # self._create_user(True)
        # self._navigate_to_client_login()
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        head = {"Accept": "application/json",
                "Content-Type": "application/json"}
        response_as_json = None

        if (expected):
            with self.client.post(url="/api/v1/users/login",
                                        headers=head,
                                        json={
                                            "username": self.user_name,
                                            "password": self.password
                                        }, name=req_label, catch_response=True) as response:
                if response.elapsed.total_seconds() > 26.0:
                    #print("Login fail response: " + str(response.elapsed.total_seconds()))
                    response.failure("Time out on login. Dropped query.")
                    to_log = {'name': req_label, 'expected': 'time_out', 'status_code': response.status_code,
                        'response_time': time.time() - start_time}
                    self.log_verbose(to_log)
                    return
                else:
                    #print("Login response: " + str(response.elapsed.total_seconds()))
                    to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                            'response_time': time.time() - start_time,
                            'response': self.try_to_read_response_as_json(response)}
                    self.log_verbose(to_log)
                    response_as_json = response.json()["data"]
        else:
            response = self.client.post(url="/api/v1/users/login",
                                        headers=head,
                                        json={
                                            "username": self.user_name,
                                            # wrong password
                                            "password": random_string_generator()
                                        }, name=req_label)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)
            response_as_json = response.json()["data"]

        if response_as_json is not None:
            token = response_as_json["token"]
            self.bearer = "Bearer " + token
            self.user_id = response_as_json["userId"]
            print("Login success with token: " + str(token))

    # purchase ticket

    def start_booking(self, expected):
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
                url="/client_ticket_book.html?tripId=" + self.trip_detail["trip_id"] + "&from=" + self.trip_detail[
                    "from"] +
                    "&to=" + self.trip_detail["to"] + "&seatType=" + self.trip_detail["seat_type"] + "&seat_price=" +
                    self.trip_detail["seat_price"] +
                    "&date=" + departure_date,
                headers=head,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
            self.log_verbose(to_log)

    def get_assurance_types(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
                url="/api/v1/assuranceservice/assurances/types",
                headers=head,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def get_foods(self, expected):
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
                url="/api/v1/foodservice/foods/" + departure_date + "/" + self.trip_detail["from"] + "/" +
                    self.trip_detail["to"] + "/" + self.trip_detail["trip_id"],
                headers=head,
                name=req_label) as response:
            # resp_data = response.json()
            # if resp_data["data"]:
            #     if random.uniform(0, 1) <= 0.5:
            #         self.food_detail = {"foodType": 2,
            #                             "foodName": resp_data["data"]["trainFoodList"][0]["foodList"][0]["foodName"],
            #                             "foodPrice": resp_data["data"]["trainFoodList"][0]["foodList"][0]["price"]}
            #     else:
            #         self.food_detail = {"foodType": 1,
            #                             "foodName": resp_data["data"]["foodStoreListMap"][self.trip_detail["from"]][0][
            #                                 "foodList"][0]["foodName"],
            #                             "foodPrice": resp_data["data"]["foodStoreListMap"][self.trip_detail["from"]][0][
            #                                 "foodList"][0]["price"]}
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def select_contact(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
            url="/api/v1/contactservice/contacts/account/" + str(self.user_id),
            headers=head,
            catch_response=True,
            name=req_label) as response_contacts:
            response_as_json_contacts = response_contacts.json()
            if not response_as_json_contacts or not "data" in response_as_json_contacts:
                response_contacts.failure("Error getting contact details")
                to_log = {'name': req_label, 'expected': expected, 'status_code': response_contacts.status_code,
                    'response_time': time.time() - start_time,
                    'response': self.try_to_read_response_as_json(response_contacts)}
                self.log_verbose(to_log)
                return

            to_log = {'name': req_label, 'expected': expected, 'status_code': response_contacts.status_code,
                    'response_time': time.time() - start_time,
                    'response': self.try_to_read_response_as_json(response_contacts)}
            self.log_verbose(to_log)

            response_as_json_contacts = response_as_json_contacts["data"]

            if len(response_as_json_contacts) == 0:
                req_label = 'set_new_contact' + postfix(expected)
                response_contacts = self.client.post(
                    url="/api/v1/contactservice/contacts",
                    headers=head,
                    json={
                        "name": self.user_id, "accountId": self.user_id, "documentType": "1",
                        "documentNumber": self.user_id, "phoneNumber": "123456"},
                    name=req_label)

                response_as_json_contacts = response_contacts.json()["data"]
                self.contactid = response_as_json_contacts["id"]
            else:
                self.contactid = response_as_json_contacts[0]["id"]

    def finish_booking(self, expected):
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if (expected):
            body_for_reservation = {
                "accountId": self.user_id,
                "contactsId": self.contactid,
                "tripId": self.trip_detail["trip_id"],
                "seatType": self.trip_detail["seat_type"],
                "date": departure_date,
                "from": self.trip_detail["from"],
                "to": self.trip_detail["to"],
                "assurance": random.choice(["0", "1"]),
                "foodType": 1,
                "foodName": "Bone Soup",
                "foodPrice": 2.5,
                "stationName": "",
                "storeName": ""
            }
            if self.food_detail:
                body_for_reservation["foodType"] = self.food_detail["foodType"]
                body_for_reservation["foodName"] = self.food_detail["foodName"]
                body_for_reservation["foodPrice"] = self.food_detail["foodPrice"]
        else:
            body_for_reservation = {
                "accountId": self.user_id,
                "contactsId": self.contactid,
                "tripId": random_string_generator(),
                "seatType": "2",
                "date": departure_date,
                "from": "Shang Hai",
                "to": "Su Zhou",
                "assurance": "0",
                "foodType": 1,
                "foodName": "Bone Soup",
                "foodPrice": 2.5,
                "stationName": "",
                "storeName": ""
            }
        start_time = time.time()
        with self.client.post(
                url="/api/v1/preserveservice/preserve",
                headers=head,
                json=body_for_reservation,
                catch_response=True,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def select_order(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        response_order_refresh = self.client.post(
            url="/api/v1/orderservice/order/refresh",
            name=req_label,
            headers=head,
            json={
                "loginId": self.user_id, "enableStateQuery": "false", "enableTravelDateQuery": "false",
                "enableBoughtDateQuery": "false", "travelDateStart": "null", "travelDateEnd": "null",
                "boughtDateStart": "null", "boughtDateEnd": "null"})

        to_log = {'name': req_label, 'expected': expected, 'status_code': response_order_refresh.status_code,
                  'response_time': time.time() - start_time,
                  'response': self.try_to_read_response_as_json(response_order_refresh)}
        self.log_verbose(to_log)

        response_as_json = response_order_refresh.json()["data"]
        if response_as_json:
            self.order_id = response_as_json[0]["id"]  # first order with paid or not paid
            self.paid_order_id = response_as_json[0]["id"]  # default first order with paid or unpaid.
        else:
            self.order_id = "sdasdasd"  # no orders, set a random number
            self.paid_order_id = "asdasdasn"
        # selecting order with payment status - not paid.
        for orders in response_as_json:
            if orders["status"] == 0:
                self.order_id = orders["id"]
                break
        for orders in response_as_json:
            if orders["status"] == 1:
                self.paid_order_id = orders["id"]
                break

    def pay(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if not self.order_id:
            to_log = {'name': req_label, 'expected': expected, 'status_code': "N/A",
                      'response_time': time.time() - start_time,
                      'response': "Place an order first!"}
            self.log_verbose(to_log)
            return
        if (expected):
            with self.client.post(
                    url="/api/v1/inside_pay_service/inside_payment",
                    headers=head,
                    json={"orderId": self.order_id, "tripId": "D1345"},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)
        else:
            with self.client.post(
                    url="/api/v1/inside_pay_service/inside_payment",
                    headers=head,
                    json={"orderId": random_string_generator(), "tripId": "D1345"},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

    # cancelNoRefund

    def cancel_with_no_refund(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if (expected):
            with self.client.get(
                    url="/api/v1/cancelservice/cancel/" + str(self.order_id) + "/" + str(self.user_id),
                    headers=head,
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

        else:
            with self.client.get(
                    url="/api/v1/cancelservice/cancel/" + self.order_id + "/" + random_string_generator(),
                    headers=head,
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

    # user refund with voucher

    def get_voucher(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if (expected):
            with self.client.post(
                    url="/getVoucher",
                    headers=head,
                    json={"orderId": self.order_id, "type": 1},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

        else:
            with self.client.post(
                    url="/getVoucher",
                    headers=head,
                    json={"orderId": random_string_generator(), "type": 1},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time}
                self.log_verbose(to_log)

    # consign ticket

    def get_consigns(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        with self.client.get(
                url="/api/v1/consignservice/consigns/order/" + self.order_id,
                headers=head,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def confirm_consign(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if (expected):
            response_as_json_consign = self.client.put(
                url="/api/v1/consignservice/consigns",
                name=req_label,
                json={
                    "accountId": self.user_id,
                    "handleDate": self.departure_date,
                    "from": self.trip_detail["from"],
                    "to": self.trip_detail["to"],
                    "orderId": self.order_id,
                    "consignee": self.order_id,
                    "phone": ''.join([random.choice(string.digits) for n in range(8)]),
                    "weight": "1",
                    "id": "",
                    "isWithin": "false"},
                headers=head)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response_as_json_consign.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_consign)}
            self.log_verbose(to_log)
        else:
            response_as_json_consign = self.client.put(
                url="/api/v1/consignservice/consigns",
                name=req_label,
                json={
                    "accountId": self.user_id,
                    "handleDate": self.departure_date,
                    "from": "Shang Hai",
                    "to": "Su Zhou",
                    "orderId": self.order_id,
                    "consignee": random_string_generator(),
                    "phone": random_string_generator(),
                    "weight": "1",
                    "id": "",
                    "isWithin": "false"}, headers=head)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response_as_json_consign.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_consign)}
            self.log_verbose(to_log)

    def collect_ticket(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if expected:
            response_as_json_collect_ticket = self.client.get(
                url="/api/v1/executeservice/execute/collected/" + self.paid_order_id,
                name=req_label,
                headers=head)
            to_log = {'name': req_label, 'expected': expected,
                      'status_code': response_as_json_collect_ticket.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_collect_ticket)}
            self.log_verbose(to_log)

    def enter_station(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if expected:
            response_as_json_enter_station = self.client.get(
                url="/api/v1/executeservice/execute/execute/" + self.paid_order_id,
                name=req_label,
                headers=head)
            to_log = {'name': req_label, 'expected': expected,
                      'status_code': response_as_json_enter_station.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_enter_station)}
            self.log_verbose(to_log)

    def perform_task(self, name):
        name_without_suffix = name.replace("_expected", "").replace("_unexpected", "")
        task = getattr(self, name_without_suffix)
        task(name.endswith('_expected'))

class Profiles:

    def callProfile(userprofile):
        task_sequence = []
        if (userprofile == 1):
            task_sequence = Profiles.login()
        if (userprofile == 2):
            task_sequence = Profiles.search_ticket()
        if (userprofile == 3):
            task_sequence = Profiles.booking()
        if (userprofile == 4):
            task_sequence = Profiles.cosign()
        if (userprofile == 5):
            task_sequence = Profiles.payment()
        if (userprofile == 6):
            task_sequence = Profiles.cancel()
        if (userprofile == 7):
            task_sequence = Profiles.collect()
        if (userprofile == 8):
            task_sequence = Profiles.adminlogin()
        if (userprofile == 9):
            task_sequence = Profiles.createusers()
        if (userprofile == 10):
            task_sequence = Profiles.getusers()
        return task_sequence


    def adminlogin():
        task_sequence = []
        logging.debug("Admin home -> login")
        task_sequence = ["loginAdmin"]
        return task_sequence

    def createusers():
        task_sequence = []
        logging.debug("Admin home -> create user")
        task_sequence = ["loginCreateUser"]
        return task_sequence

    def getusers():
        task_sequence = []
        logging.debug("Admin home -> create user")
        task_sequence = ["loginAdmin","adminGetUsers"]
        return task_sequence

    def login():
        task_sequence = []
        logging.debug("User home -> login")
        number = random.randint(1, 100)/100
        if number < 0.98:
            task_sequence = ["login_expected"]
        else:
            task_sequence = ["login_unexpected"]
        return task_sequence

    def search_ticket():
        task_sequence = []
        logging.debug("Running user 'only search'...")
        task_sequence = ["home_expected", "search_ticket_expected"]
        return task_sequence
    
    def booking():
        task_sequence = []
        logging.debug("Running user 'booking'...")

        task_sequence = ["home_expected",
                        "login_expected",
                        "search_ticket_expected",
                        "start_booking_expected",
                        "get_assurance_types_expected",
                        "get_foods_expected",
                        "select_contact_expected",
                        "finish_booking_expected"]
        return task_sequence

    def cosign():
        task_sequence = []
        logging.debug("Running user 'consign ticket'...")
        task_sequence = [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "get_consigns_expected",
            "confirm_consign_expected",
        ]
        return task_sequence

    def payment():
        task_sequence = []
        logging.debug("Running user 'booking with payment'...")
        task_sequence = ["home_expected",
                        "login_expected",
                        "select_contact_expected",
                        "finish_booking_expected",
                        "select_order_expected",
                        "pay_expected"]
        return task_sequence

    def cancel():
        task_sequence = []
        logging.debug("Running user 'cancel no refund'...")
        task_sequence = [
            "home_expected",
            "login_expected",
            "select_order_expected",
            "cancel_with_no_refund_expected",
        ]
        return task_sequence

    def collect():
        task_sequence = []
        logging.debug("Running user 'collect ticket'...")
        task_sequence = [
            "home_expected",
            "login_expected",
            "select_order_expected",
            "pay_expected",
            "collect_ticket_expected",
        ]
        return task_sequence
        
class UserActionSet1(HttpUser):
    global max_experiment_duration
    weight = 1
    #Long wait time so each user will execute only one task and then wait idle to the end
    wait_time = constant(max_experiment_duration)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        bearer = 0
        global user_count
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        sleep_time = ((random.expovariate(1) * stage_users) % (stage_duration-stage_duration_passed)) #expovariate defines the average rate of user arrivals per second, for example expovariate(1) will result to an average user arrival of 1 user per second) 
        user_count += 1
        userprofile = random.randint(2, 2)
        print("User "+str(user_count)+" with profile "+str(userprofile)+" will start at tick "+str(sleep_time))
        time.sleep(sleep_time)
        task_sequence = Profiles.callProfile(userprofile)
        request = Requests(self.client)
        for tasks in task_sequence:
            request.perform_task(tasks)

class UserActionSet2(HttpUser):
    global max_experiment_duration
    weight = 1
    #Long wait time so each user will execute only one task and then wait idle to the end
    wait_time = constant(max_experiment_duration)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        global user_count
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        sleep_time = ((random.expovariate(1) * stage_users) % (stage_duration-stage_duration_passed)) #expovariate defines the average rate of user arrivals per second, for example expovariate(1) will result to an average user arrival of 1 user per second) 
        user_count += 1
        userprofile = random.randint(3, 7)
        print("User "+str(user_count)+" with profile "+str(userprofile)+" will start at tick "+str(sleep_time))
        time.sleep(sleep_time)
        task_sequence = Profiles.callProfile(userprofile)
        request = Requests(self.client)
        for tasks in task_sequence:
            request.perform_task(tasks)

class UserActionSet3(HttpUser):
    global max_experiment_duration
    weight = 1
    #Long wait time so each user will execute only one task and then wait idle to the end
    wait_time = constant(max_experiment_duration)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        global user_count
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        sleep_time = ((random.expovariate(1) * stage_users) % (stage_duration-stage_duration_passed)) #expovariate defines the average rate of user arrivals per second, for example expovariate(1) will result to an average user arrival of 1 user per second) 
        user_count += 1
        userprofile = random.randint(1, 1)
        print("User "+str(user_count)+" with profile "+str(userprofile)+" will start at tick "+str(sleep_time))
        time.sleep(sleep_time)
        task_sequence = Profiles.callProfile(userprofile)
        request = Requests(self.client)
        for tasks in task_sequence:
            request.perform_task(tasks)

class UserActionSet4(HttpUser):
    global max_experiment_duration
    weight = 1
    #Long wait time so each user will execute only one task and then wait idle to the end
    wait_time = constant(max_experiment_duration)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        global user_count
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        sleep_time = ((random.expovariate(1) * stage_users) % (stage_duration-stage_duration_passed)) #expovariate defines the average rate of user arrivals per second, for example expovariate(1) will result to an average user arrival of 1 user per second) 
        user_count += 1
        userprofile = random.randint(8, 8)
        print("User "+str(user_count)+" with profile "+str(userprofile)+" will start at tick "+str(sleep_time))
        time.sleep(sleep_time)
        task_sequence = Profiles.callProfile(userprofile)
        request = Requests(self.client)
        for tasks in task_sequence:
            request.perform_task(tasks)

class UserActionSet5(HttpUser):
    global max_experiment_duration
    weight = 1
    #Long wait time so each user will execute only one task and then wait idle to the end
    wait_time = constant(max_experiment_duration)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        global user_count
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        sleep_time = ((random.expovariate(1) * stage_users) % (stage_duration-stage_duration_passed)) #expovariate defines the average rate of user arrivals per second, for example expovariate(1) will result to an average user arrival of 1 user per second) 
        user_count += 1
        userprofile = random.randint(9, 9)
        print("User "+str(user_count)+" with profile "+str(userprofile)+" will start at tick "+str(sleep_time))
        time.sleep(sleep_time)
        task_sequence = Profiles.callProfile(userprofile)
        request = Requests(self.client)
        for tasks in task_sequence:
            request.perform_task(tasks)

class UserActionSet6(HttpUser):
    global max_experiment_duration
    weight = 1
    #Long wait time so each user will execute only one task and then wait idle to the end
    wait_time = constant(max_experiment_duration)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        global user_count
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        sleep_time = ((random.expovariate(1) * stage_users) % (stage_duration-stage_duration_passed)) #expovariate defines the average rate of user arrivals per second, for example expovariate(1) will result to an average user arrival of 1 user per second) 
        user_count += 1
        userprofile = random.randint(10, 10)
        print("User "+str(user_count)+" with profile "+str(userprofile)+" will start at tick "+str(sleep_time))
        time.sleep(sleep_time)
        task_sequence = Profiles.callProfile(userprofile)
        request = Requests(self.client)
        for tasks in task_sequence:
            request.perform_task(tasks)

# Class that does nothing to allow users to slow down and complete the work
class UserSlowdown(HttpUser):
    weight = 1
    #wait_function = random.expovariate(1) * 100
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        pass

class StagesShapeWithCustomUsers(LoadTestShape):

    #stages = [
    #    {"duration": 20, "users": 10, "spawn_rate": 100, "user_classes": [UserActionSet1]},
    #    {"duration": 40, "users": 50, "spawn_rate": 50, "user_classes": [UserActionSet1]},
    #    {"duration": 60, "users": 50, "spawn_rate": 50, "user_classes": [UserActionSet1]},
    #    {"duration": 90, "users": 100, "spawn_rate": 100, "user_classes": [UserActionSet1]},
    #    {"duration": 120, "users": 80, "spawn_rate": 80, "user_classes": [UserActionSet1]},
    #    {"duration": 140, "users": 90, "spawn_rate": 90, "user_classes": [UserActionSet1]},
    #    {"duration": 160, "users": 70, "spawn_rate": 70, "user_classes": [UserActionSet1]},
    #    {"duration": 180, "users": 20, "spawn_rate": 20, "user_classes": [UserActionSet1]},
    #    ]

    stages = [
        {"duration": 10, "users": 50, "spawn_rate": 50, "user_classes": [UserActionSet1]},
        {"duration": 30, "users": 500, "spawn_rate": 500, "user_classes": [UserActionSet2]},]

    #stages = [{"duration": 100, "users": 10000, "spawn_rate": 10000, "user_classes": [UserActionSet3]}]
    #stages = [{"duration": 10, "users": 10, "spawn_rate": 10}]
    stages = [
        {"duration": 10, "users": 1, "spawn_rate": 1, "user_classes": [UserActionSet4]},
        {"duration": 1000, "users": 500, "spawn_rate": 500, "user_classes": [UserActionSet5]},
        {"duration": 1500, "users": 500, "spawn_rate": 500, "user_classes": [UserActionSet1]},]
    stages = [
        {"duration": 5, "users": 1, "spawn_rate": 1, "user_classes": [UserActionSet6]},
        {"duration": 1000, "users": 1000, "spawn_rate": 1000, "user_classes": [UserActionSet3]},]

    def tick(self):
        global stage_duration
        global stage_duration_passed
        global stage_users
        global stage_rate
        global max_experiment_duration
        run_time = self.get_run_time()
        print("Tick: " + str(run_time))
        for stage in self.stages:
            if run_time < stage["duration"]:
                if (max_experiment_duration < run_time):
                    print("ERROR!!! Experiment exceeded max duration time ("+str(max_experiment_duration)+" seconds)")
                    return None
                if (stage_duration != stage["duration"]):
                    stage_duration_passed = stage_duration
                    print ("Updating stage duration")
                stage_duration = stage["duration"]
                stage_users = stage["users"]
                stage_rate = stage["spawn_rate"]
                print("Stage duration: " + str(stage_duration))
                try:
                    tick_data = (stage["users"], stage["spawn_rate"], stage["user_classes"])
                except:
                    tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data

        return None


"""
Events for printing all requests into a file. 
"""


class Print:  # pylint: disable=R0902
    """
    Record every response (useful when debugging a single locust)
    """

    def __init__(self, env: locust.env.Environment, include_length=False, include_time=False):
        self.env = env
        self.env.events.request_success.add_listener(self.request_success)

    def request_success(self, request_type, name, response_time, response_length, **_kwargs):
        users = self.env.runner.user_count
        data = [datetime.now(), request_type, name, response_time, users]
        state_data.append(data)


@events.init.add_listener
def locust_init_listener(environment, **kwargs):
    Print(env=environment)


@events.quitting.add_listener
def write_statistics(environment, **kwargs):
    with open("output/requests_stats_u250_c.csv", "a+") as f:
        csv_writer = csv.writer(f)
        for row in state_data:
            csv_writer.writerow(row)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global user_count
    global stage_duration_passed
    # deterministic profile selection
    print("Setting seed number")
    random.seed(123)
    user_count = 0
    stage_duration_passed = 0
    if not isinstance(environment.runner, MasterRunner):
        print("Beginning test setup")
    else:
        print("Started test from Master node")
