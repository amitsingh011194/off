import pymysql
import pymysql.cursors
import requests
from datetime import datetime
import json
import sys
from boto3 import client, resource

# Importing Functions

from helper_functions import logger, get_parameter_from_ssm, get_client_name

TodayDate = datetime.today().date()

def lambda_handler(event, context):

	logger.info(f"Event: {json.dumps(event)}")
	logger.info("started Report lambda")

	global connection, bank, cursor, ssm

	# Getting event variables
	bank = get_client_name(event['bank_code'])
	bank_code = event['bank_code']
	run_no = event['run_no']
	zone = event['zone']

	ssm = client("ssm")
	cp = client('customer-profiles')

	# Getting Database Details from SSM
	dbname = get_parameter_from_ssm(ssm, "SSP_DB_NAME", bank)
	user = get_parameter_from_ssm(ssm, "SSP_DB_USER", bank)
	password = get_parameter_from_ssm(ssm, "SSP_DB_PASSWORD", bank)
	host = get_parameter_from_ssm(ssm, "SSP_DB_HOST", bank)
	port = get_parameter_from_ssm(ssm, "SSP_DB_PORT", bank)

	# Getting other Details from SSM
	domain = get_parameter_from_ssm(ssm, "CONNECT_DOMAIN", bank)
	lm_url = get_parameter_from_ssm(ssm, "CONDUENT_LINK", bank)


	try:
		# Connect to the database
		connection = pymysql.connect(
			host=host,
			user=user,
			password=password,
			database=dbname,
			port=int(port),
			sql_mode="",
		)

		logger.info(f"Connection to Database Successful: {connection}")

	except pymysql.MySQLError as e:
		logger.error(f"Error during connecting to database: {e}")
		return e
	

	logger.info("Starting the lambda for previous customer profile deletion")
	if connection:
		try:
			if run_no == "1":
				query = f"select * from customer_profile"
			else:
				query = f"select * from customer_profile where zone_code = '{zone}'"
			cursor = connection.cursor(pymysql.cursors.DictCursor)
			cursor.execute(query)
			result = cursor.fetchall()
			logger.info(f"Query Fetched Successfully. Query for deleting zone {zone} is {query}. Length: {len(result)}")

			for row in result:
				id = row['id']
				shawkey = row['shawkey']
				zone_code = row['zone_code']
				first_name = row['first_name']
				last_name = row['last_name']
				address = row['address']
				city = row['city']
				state = row['state']
				zip_code = row['zip_code']
				phone_number = row['phone_number']
				date_of_birth = f"{row['date_of_birth']}"
				email = row['email']
				ssn = row['ssn']
				run1 = row['run1']
				run2 = row['run2']
				run3 = row['run3']
				created_at = row['created_at']
				updated_at = row['updated_at']
				profile_id = row['profile_id']
				dataloadingdate = row['dataloadingdate']

				try:
					response = cp.delete_profile(
								DomainName=domain,
								ProfileId=profile_id)
					
					logger.info(f"Resposne for deleting {profile_id} is {response}")
				except Exception as e:
					logger.error(f"Error during trying to remove the profile {profile_id} from customer profiles in connect. Error: {e}")
					response = {"Message":"NOTOK"}

				if response.get('Message') == "OK":
					logger.info(f"successfully deleted the profile {profile_id} for shawkey: {shawkey}")
				else:
					logger.error(f"Error during deleting the profile {profile_id}. Error: {response.get('Message')}")
				
				try:
					delete_query = f"DELETE FROM customer_profile WHERE id = {id}"
					cursor.execute(delete_query)
					connection.commit()
				except Exception as e:
					logger.error(f"Error during deleting record {profile_id} from database for id {id}.")
		except pymysql.MySQLError as e:
			logger.error(f"Error executing query for all records of customer profiles for deletion task. Error: {e}")
			return e
	else:
		logger.error("Connection lost during deletion task")
		
	if run_no == "1":
		query = f"select * from customer_profile_history where run1 = '1' and dataloadingdate = '{TodayDate}'"
	elif run_no == "2":
		query = f"select * from customer_profile_history where run2 = '1' and dataloadingdate = '{TodayDate}' and zone_code = '{zone}'"
	elif run_no == "3":
		query = f"select * from customer_profile_history where run3 = '1' and dataloadingdate = '{TodayDate}' and zone_code = '{zone}'"
	else:
		logger.error("run_no is not correct.")
		return {"res": "failed"}

	logger.info(f"Query for run {run_no} for zone {zone}: {query}")
	if connection:
		try:
			cursor = connection.cursor(pymysql.cursors.DictCursor)
			cursor.execute(query)
			result = cursor.fetchall()
			logger.info(f"Query Fetched Successfully. Query: {query}. Length: {len(result)}.")

			for row in result:
				id = row['id']
				shawkey = row['shawkey']
				zone_code = row['zone_code']
				first_name = row['first_name']
				last_name = row['last_name']
				address = row['address']
				city = row['city']
				state = row['state']
				zip_code = row['zip_code']
				phone_number = row['phone_number']
				date_of_birth = str(row['date_of_birth'])
				email = row['email']
				ssn = row['ssn']
				run1 = row['run1']
				run2 = row['run2']
				run3 = row['run3']
				created_at = row['created_at']
				updated_at = row['updated_at']
				profile_id = row['profile_id']
				dataloadingdate = row['dataloadingdate']
				multiple_loan_flag = row['multiple_loan_flag']
				conduent = lm_url+shawkey

				response = cp.create_profile(
					DomainName=domain,
					AccountNumber=shawkey,
					FirstName=first_name,
					LastName=last_name,
					BirthDate=date_of_birth,
					PhoneNumber=phone_number,
					MobilePhoneNumber=phone_number,
					EmailAddress=email,
					Address={
						'Address1': address,
						'City': city,
						'State': state,
						'Country': 'US',
						'PostalCode': zip_code
					},
					Attributes={
						'SSN': ssn,
						'Link': conduent,
						'Zone': zone_code,
						'Run': run_no,
						'MultipleLoan': multiple_loan_flag
					})

				logger.info(f"response for {shawkey} is {response}")

				new_profile_id = response.get('ProfileId')

				if new_profile_id:
					# Update the profile_id with data in the database
					try:
						sql_query = '''INSERT INTO customer_profile (
															shawkey, zone_code, first_name, last_name, 
															address, city, state, zip_code, phone_number, 
															date_of_birth, email, ssn, profile_id,dataloadingdate,multiple_loan_flag) 
												VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

						cursor.execute(sql_query, (
							row['shawkey'], row['zone_code'], row['first_name'], row['last_name'],
							row['address'], row['city'], row['state'], row['zip_code'], row['phone_number'],
							row['date_of_birth'], row['email'], row['ssn'], new_profile_id, row['dataloadingdate'],multiple_loan_flag
						))

						connection.commit()
						logger.info(f"Successfully entered data in customer_profile for {shawkey} with profile ID {new_profile_id}")
					except Exception as e:
						logger.error(f"An error occurred while inserting the data into customer_profile for {shawkey}: {e}")


					logger.info(f"Profile created successfully. Profile ID: {new_profile_id} for Customer ID: {shawkey}")
				else:
					logger.error(f"Profile creation failed for Customer ID: {shawkey}, no Profile ID returned in response.")
		except pymysql.MySQLError as e:
			logger.error(f"Error executing query. Error: {e}")
			return e
	else:
		logger.error("Connection lost during fetching from history table task")

	logger.info("Lambda Ended.")
	return {"res":"success"}
