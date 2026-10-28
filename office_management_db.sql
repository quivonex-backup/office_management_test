-- MySQL dump 10.13  Distrib 8.0.32, for Win64 (x86_64)
--
-- Host: localhost    Database: office_management_db
-- ------------------------------------------------------
-- Server version	8.0.32

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `accounts_emailotp`
--

DROP TABLE IF EXISTS `accounts_emailotp`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_emailotp` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(254) NOT NULL,
  `otp` varchar(6) NOT NULL,
  `purpose` varchar(30) DEFAULT NULL,
  `is_verified` tinyint(1) NOT NULL,
  `attempts` smallint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `expires_at` datetime(6) NOT NULL,
  `verified_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `accounts_emailotp_email_d0b1e7f0` (`email`),
  CONSTRAINT `accounts_emailotp_chk_1` CHECK ((`attempts` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_emailotp`
--

LOCK TABLES `accounts_emailotp` WRITE;
/*!40000 ALTER TABLE `accounts_emailotp` DISABLE KEYS */;
INSERT INTO `accounts_emailotp` VALUES (1,'sohamsapkal004@gmail.com','005940','FORGOT_PASSWORD',0,5,'2026-08-03 09:23:15.570921','2026-08-03 09:28:15.556391',NULL),(2,'sohamsapkl004@gmail.com','302427','FORGOT_PASSWORD',0,0,'2026-08-03 09:28:15.485810','2026-08-03 09:28:44.701518',NULL),(3,'sohamsapkl004@gmail.com','593381','FORGOT_PASSWORD',0,1,'2026-08-03 09:28:45.159617','2026-08-03 09:33:45.140125',NULL),(4,'sohamsapkal004@gmail.com','604391','FORGOT_PASSWORD',0,0,'2026-08-03 09:30:11.377683','2026-08-03 09:35:11.364559',NULL),(5,'sohamsapkal004@gmail.com','862564','FORGOT_PASSWORD',1,0,'2026-08-03 09:38:36.982667','2026-08-03 09:43:36.952322','2026-08-03 09:39:34.915618');
/*!40000 ALTER TABLE `accounts_emailotp` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_role`
--

DROP TABLE IF EXISTS `accounts_role`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_role` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_role`
--

LOCK TABLES `accounts_role` WRITE;
/*!40000 ALTER TABLE `accounts_role` DISABLE KEYS */;
INSERT INTO `accounts_role` VALUES (1,'admin',1,'2026-08-02 10:24:50.900822','2026-08-02 10:40:34.607622'),(2,'accountant',1,'2026-08-02 11:07:38.775679','2026-08-02 11:07:38.775679');
/*!40000 ALTER TABLE `accounts_role` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_user`
--

DROP TABLE IF EXISTS `accounts_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `email` varchar(254) NOT NULL,
  `mobile` varchar(15) NOT NULL,
  `profile_photo` varchar(100) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `role_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `mobile` (`mobile`),
  KEY `accounts_user_role_id_a6dd19b0_fk_accounts_role_id` (`role_id`),
  CONSTRAINT `accounts_user_role_id_a6dd19b0_fk_accounts_role_id` FOREIGN KEY (`role_id`) REFERENCES `accounts_role` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_user`
--

LOCK TABLES `accounts_user` WRITE;
/*!40000 ALTER TABLE `accounts_user` DISABLE KEYS */;
INSERT INTO `accounts_user` VALUES (1,'pbkdf2_sha256$1000000$D0NX7MEqqKxAiwRFAaLfkR$XFoU8nUx3L7xkV4Uul/olncT+6NZaXhv1bULR8kX2ns=',NULL,1,'admin','','',1,1,'2026-08-02 10:13:18.625582','sravanfakesinha@gmail.com','','','2026-08-02 10:13:19.166155','2026-08-02 10:19:54.421022',NULL),(2,'pbkdf2_sha256$1000000$dWCeVhzIFuO9lNt3lTFOCY$UZ5PQ9wW+2bdpyMedd9oMELoSHUnuT0JNwBh9PqJSIY=',NULL,0,'soham','Soham','Sapkal',0,1,'2026-08-02 11:10:51.862083','sohamsapkal004@gmail.com','9876543211','users/profile/07f5e43f05ca4474bc9f369e0762cb42.jpeg','2026-08-02 11:10:52.323701','2026-08-03 09:45:13.517213',1),(3,'pbkdf2_sha256$1000000$S9PhABye43q7PfrR4rmkd3$Kq6keJvM+PUgDoIP2G2RmQMKZFWQU/dXu4vWy6vxqD0=',NULL,0,'aditya123','Aditya','Kadam',0,1,'2026-08-03 09:13:01.475991','kadamaditya@gmail.com','9876543275','users/profile/a0da515aaeae4cbc8316072c37d6aaca.jpg','2026-08-03 09:13:01.707253','2026-08-03 09:13:01.707295',1),(4,'pbkdf2_sha256$1000000$U5HvcDX2bZoCdR9r49O7Cl$3b7KaWkvkWZmx1giL1GlM1jFfiIBn66FYmzd+pRUdd4=',NULL,0,'aditya','Aditya','Kadam',0,1,'2026-08-03 09:16:35.716019','kadamaditya88332@gmail.com','9876543210','users/profile/fc9b9d63faa54e3b86acbd2d469ca71f.jpg','2026-08-03 09:16:36.011803','2026-08-03 09:16:36.011848',1);
/*!40000 ALTER TABLE `accounts_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_user_groups`
--

DROP TABLE IF EXISTS `accounts_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_user_groups_user_id_group_id_59c0b32f_uniq` (`user_id`,`group_id`),
  KEY `accounts_user_groups_group_id_bd11a704_fk_auth_group_id` (`group_id`),
  CONSTRAINT `accounts_user_groups_group_id_bd11a704_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `accounts_user_groups_user_id_52b62117_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_user_groups`
--

LOCK TABLES `accounts_user_groups` WRITE;
/*!40000 ALTER TABLE `accounts_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_user_user_permissions`
--

DROP TABLE IF EXISTS `accounts_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_user_user_permi_user_id_permission_id_2ab516c2_uniq` (`user_id`,`permission_id`),
  KEY `accounts_user_user_p_permission_id_113bb443_fk_auth_perm` (`permission_id`),
  CONSTRAINT `accounts_user_user_p_permission_id_113bb443_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `accounts_user_user_p_user_id_e4f0a161_fk_accounts_` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_user_user_permissions`
--

LOCK TABLES `accounts_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `accounts_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `audit_activitylog`
--

DROP TABLE IF EXISTS `audit_activitylog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_activitylog` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `action` varchar(50) NOT NULL,
  `module` varchar(100) DEFAULT NULL,
  `object_type` varchar(100) DEFAULT NULL,
  `object_id` varchar(100) DEFAULT NULL,
  `description` longtext,
  `old_data` json DEFAULT NULL,
  `new_data` json DEFAULT NULL,
  `ip_address` char(39) DEFAULT NULL,
  `user_agent` longtext,
  `request_method` varchar(10) DEFAULT NULL,
  `request_path` longtext,
  `created_at` datetime(6) NOT NULL,
  `user_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `audit_activitylog_module_5f759e5b` (`module`),
  KEY `audit_activitylog_object_id_dca27810` (`object_id`),
  KEY `audit_activitylog_created_at_302c2837` (`created_at`),
  KEY `audit_activ_user_id_82a5c3_idx` (`user_id`,`created_at`),
  KEY `audit_activ_module_fb8b98_idx` (`module`,`action`),
  CONSTRAINT `audit_activitylog_user_id_3cff121f_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_activitylog`
--

LOCK TABLES `audit_activitylog` WRITE;
/*!40000 ALTER TABLE `audit_activitylog` DISABLE KEYS */;
INSERT INTO `audit_activitylog` VALUES (1,'UPDATE','ROLE','Role','1','Role \'admin\' updated.','{\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:24:50.901828Z\"}','{\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}','127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/role/update/','2026-08-02 10:40:34.643647',1),(2,'LOGIN','AUTH','User','1','User \'admin\' logged in successfully.',NULL,NULL,'127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-02 11:05:06.369679',1),(3,'CREATE','ROLE','Role','2','Role \'accountant\' created.',NULL,'{\"id\": 2, \"name\": \"accountant\", \"is_active\": true, \"created_at\": \"2026-08-02T11:07:38.775679Z\", \"updated_at\": \"2026-08-02T11:07:38.775679Z\"}','127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/role/create/','2026-08-02 11:07:38.825809',1),(4,'CREATE','USER','User','2','User \'soham\' created.',NULL,'{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-02T11:10:52.323701Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/8a7a556d8172417faaba2d99ecf85300.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAQUGSTGHYRZUZAVLH%2F20260802%2Fap-south-1%2Fs3%2Faws4_request&X-Amz-Date=20260802T111052Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=f21c790097de1a9827caf9781ab5f72c61e8fb7c28c4145898519d1f84a86507\"}','127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/register/','2026-08-02 11:10:52.355593',1),(5,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-02 11:20:41.866544',2),(6,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-02 11:21:14.941673',2),(7,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-02 11:35:06.714143',2),(8,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-02 11:36:01.203795',2),(9,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'127.0.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-02 11:39:21.224602',2),(10,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-03 06:46:46.966037',2),(11,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-03 07:35:51.730633',2),(12,'UPDATE','USER','User','2','User \'soham\' updated.','{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-02T11:10:52.323701Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/8a7a556d8172417faaba2d99ecf85300.jpg\"}','{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-03T07:40:26.397085Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/7aab1cad4a404bd7879bac39761f799b.jpeg\"}','172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/user/update/','2026-08-03 07:40:26.602285',2),(13,'UPDATE','USER','User','2','User \'soham\' updated own profile.','{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-03T07:40:26.397085Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/7aab1cad4a404bd7879bac39761f799b.jpeg\"}','{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-03T08:37:32.512481Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/07f5e43f05ca4474bc9f369e0762cb42.jpeg\"}','172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/my-profile/update/','2026-08-03 08:37:32.688426',2),(14,'LOGIN','AUTH','User','1','User \'admin\' logged in successfully.',NULL,NULL,'172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-03 09:12:25.315816',1),(15,'CREATE','USER','User','3','User \'aditya\' created.',NULL,'{\"id\": 3, \"role\": 1, \"email\": \"kadamaditya88332@gmail.com\", \"mobile\": \"9876543210\", \"username\": \"aditya\", \"is_active\": true, \"last_name\": \"Kadam\", \"created_at\": \"2026-08-03T09:13:01.707253Z\", \"first_name\": \"Aditya\", \"updated_at\": \"2026-08-03T09:13:01.707295Z\", \"date_joined\": \"2026-08-03T09:13:01.475991Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/a0da515aaeae4cbc8316072c37d6aaca.jpg\"}','172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/register/','2026-08-03 09:13:01.862136',1),(16,'CREATE','USER','User','4','User \'aditya\' created.',NULL,'{\"id\": 4, \"role\": 1, \"email\": \"kadamaditya88332@gmail.com\", \"mobile\": \"9876543210\", \"username\": \"aditya\", \"is_active\": true, \"last_name\": \"Kadam\", \"created_at\": \"2026-08-03T09:16:36.011803Z\", \"first_name\": \"Aditya\", \"updated_at\": \"2026-08-03T09:16:36.011848Z\", \"date_joined\": \"2026-08-03T09:16:35.716019Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/fc9b9d63faa54e3b86acbd2d469ca71f.jpg\"}','172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/register/','2026-08-03 09:16:36.239433',1),(17,'LOGIN','AUTH','User','2','User \'soham\' logged in successfully.',NULL,NULL,'172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/login/','2026-08-03 09:21:38.865782',2),(18,'PASSWORD_CHANGE','USER','User','2','User \'soham\' changed password.',NULL,NULL,'172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/change-password/','2026-08-03 09:35:47.255804',2),(19,'PASSWORD_RESET','AUTH','User','2','Password reset for user \'soham\'.',NULL,NULL,'172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/forgot-password/','2026-08-03 09:42:02.376717',2),(20,'UPDATE','USER','User','2','User \'soham\' updated own profile.','{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-03T09:42:02.320132Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/07f5e43f05ca4474bc9f369e0762cb42.jpeg\"}','{\"id\": 2, \"role\": 1, \"email\": \"sohamsapkal004@gmail.com\", \"mobile\": \"9876543211\", \"username\": \"soham\", \"is_active\": true, \"last_name\": \"Sapkal\", \"created_at\": \"2026-08-02T11:10:52.323701Z\", \"first_name\": \"Soham\", \"updated_at\": \"2026-08-03T09:45:13.517213Z\", \"date_joined\": \"2026-08-02T11:10:51.862083Z\", \"role_details\": {\"id\": 1, \"name\": \"admin\", \"is_active\": true, \"created_at\": \"2026-08-02T10:24:50.900822Z\", \"updated_at\": \"2026-08-02T10:40:34.607622Z\"}, \"profile_photo\": \"https://employee-attendance-media.s3.amazonaws.com/users/profile/07f5e43f05ca4474bc9f369e0762cb42.jpeg\"}','172.18.0.1','PostmanRuntime/7.51.1','POST','/accounts/my-profile/update/','2026-08-03 09:45:13.552457',2);
/*!40000 ALTER TABLE `audit_activitylog` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add content type',4,'add_contenttype'),(14,'Can change content type',4,'change_contenttype'),(15,'Can delete content type',4,'delete_contenttype'),(16,'Can view content type',4,'view_contenttype'),(17,'Can add session',5,'add_session'),(18,'Can change session',5,'change_session'),(19,'Can delete session',5,'delete_session'),(20,'Can view session',5,'view_session'),(21,'Can add email otp',6,'add_emailotp'),(22,'Can change email otp',6,'change_emailotp'),(23,'Can delete email otp',6,'delete_emailotp'),(24,'Can view email otp',6,'view_emailotp'),(25,'Can add role',7,'add_role'),(26,'Can change role',7,'change_role'),(27,'Can delete role',7,'delete_role'),(28,'Can view role',7,'view_role'),(29,'Can add user',8,'add_user'),(30,'Can change user',8,'change_user'),(31,'Can delete user',8,'delete_user'),(32,'Can view user',8,'view_user'),(33,'Can add activity log',9,'add_activitylog'),(34,'Can change activity log',9,'change_activitylog'),(35,'Can delete activity log',9,'delete_activitylog'),(36,'Can view activity log',9,'view_activitylog'),(37,'Can add client',10,'add_client'),(38,'Can change client',10,'change_client'),(39,'Can delete client',10,'delete_client'),(40,'Can view client',10,'view_client'),(41,'Can add client document',11,'add_clientdocument'),(42,'Can change client document',11,'change_clientdocument'),(43,'Can delete client document',11,'delete_clientdocument'),(44,'Can view client document',11,'view_clientdocument');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `client_documents`
--

DROP TABLE IF EXISTS `client_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_documents` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(200) DEFAULT NULL,
  `file` varchar(100) DEFAULT NULL,
  `description` longtext,
  `created_at` datetime(6) NOT NULL,
  `client_id` bigint NOT NULL,
  `uploaded_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `client_documents_client_id_d520829b_fk_clients_id` (`client_id`),
  KEY `client_documents_uploaded_by_id_d8cc46ac_fk_accounts_user_id` (`uploaded_by_id`),
  CONSTRAINT `client_documents_client_id_d520829b_fk_clients_id` FOREIGN KEY (`client_id`) REFERENCES `clients` (`id`),
  CONSTRAINT `client_documents_uploaded_by_id_d8cc46ac_fk_accounts_user_id` FOREIGN KEY (`uploaded_by_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `client_documents`
--

LOCK TABLES `client_documents` WRITE;
/*!40000 ALTER TABLE `client_documents` DISABLE KEYS */;
/*!40000 ALTER TABLE `client_documents` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `clients`
--

DROP TABLE IF EXISTS `clients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clients` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `client_code` varchar(20) NOT NULL,
  `client_name` varchar(150) NOT NULL,
  `company_name` varchar(200) DEFAULT NULL,
  `mobile` varchar(20) DEFAULT NULL,
  `email` varchar(254) DEFAULT NULL,
  `gst_number` varchar(15) DEFAULT NULL,
  `address` longtext,
  `country` varchar(100) DEFAULT NULL,
  `state` varchar(100) DEFAULT NULL,
  `city` varchar(100) DEFAULT NULL,
  `pincode` varchar(10) DEFAULT NULL,
  `notes` longtext,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `created_by_id` bigint DEFAULT NULL,
  `updated_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `client_code` (`client_code`),
  KEY `clients_created_by_id_bd0ce932_fk_accounts_user_id` (`created_by_id`),
  KEY `clients_updated_by_id_09589439_fk_accounts_user_id` (`updated_by_id`),
  KEY `clients_is_active_ae550253` (`is_active`),
  CONSTRAINT `clients_created_by_id_bd0ce932_fk_accounts_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `clients_updated_by_id_09589439_fk_accounts_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `clients`
--

LOCK TABLES `clients` WRITE;
/*!40000 ALTER TABLE `clients` DISABLE KEYS */;
/*!40000 ALTER TABLE `clients` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_accounts_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (6,'accounts','emailotp'),(7,'accounts','role'),(8,'accounts','user'),(1,'admin','logentry'),(9,'audit','activitylog'),(3,'auth','group'),(2,'auth','permission'),(10,'clients','client'),(11,'clients','clientdocument'),(4,'contenttypes','contenttype'),(5,'sessions','session');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2026-08-02 09:48:22.108176'),(2,'contenttypes','0002_remove_content_type_name','2026-08-02 09:48:22.206990'),(3,'auth','0001_initial','2026-08-02 09:48:22.628252'),(4,'auth','0002_alter_permission_name_max_length','2026-08-02 09:48:22.701584'),(5,'auth','0003_alter_user_email_max_length','2026-08-02 09:48:22.712442'),(6,'auth','0004_alter_user_username_opts','2026-08-02 09:48:22.722223'),(7,'auth','0005_alter_user_last_login_null','2026-08-02 09:48:22.731698'),(8,'auth','0006_require_contenttypes_0002','2026-08-02 09:48:22.739351'),(9,'auth','0007_alter_validators_add_error_messages','2026-08-02 09:48:22.750206'),(10,'auth','0008_alter_user_username_max_length','2026-08-02 09:48:22.761296'),(11,'auth','0009_alter_user_last_name_max_length','2026-08-02 09:48:22.770423'),(12,'auth','0010_alter_group_name_max_length','2026-08-02 09:48:22.821611'),(13,'auth','0011_update_proxy_permissions','2026-08-02 09:48:22.853015'),(14,'auth','0012_alter_user_first_name_max_length','2026-08-02 09:48:22.885147'),(15,'accounts','0001_initial','2026-08-02 09:48:23.362786'),(16,'admin','0001_initial','2026-08-02 09:48:23.505240'),(17,'admin','0002_logentry_remove_auto_add','2026-08-02 09:48:23.537284'),(18,'admin','0003_logentry_add_action_flag_choices','2026-08-02 09:48:23.544529'),(19,'audit','0001_initial','2026-08-02 09:48:23.721155'),(20,'sessions','0001_initial','2026-08-02 09:48:23.774131'),(21,'clients','0001_initial','2026-08-03 11:31:44.544303');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-03 17:04:00
