# Fitness Club Management System

A web-based **Fitness Club Management System** built with **Flask** and **SQLite**.  
This app allows gym administrators to manage members, trainers, classes, payments, and check-ins, with automated membership reminders and dashboards for key statistics.

---

##  Understanding the System

**This is a staff-facing management system for fitness club employees, NOT a public membership portal.** Here's how it works:

- **For Members:** People sign up IN PERSON at the physical gym location
- **For Staff:** Gym employees use this system to manage member accounts, track payments, schedule classes, and handle check-ins
- **Member Access:** Members don't log into this system - they get physical access cards and staff manages their accounts

## Staff Member Workflow:
1. **Login** with staff credentials
2. **Add New Members** when people sign up at front desk
3. **Process Payments** for membership fees
4. **Schedule Classes** and assign trainers
5. **Track Check-ins** as members arrive
6. **Send Reminders** for expiring memberships

## Typical Member Journey:
1. 👤 Signs up IN PERSON at gym
2. 📝 Staff creates account in this system
3. 💳 Pays membership fee at front desk
4. 🏋️ Gets physical access card/key fob
5. ✅ Checks in by scanning card at gym entrance
6. 📱 Receives SMS reminders (simulated) when membership nears expiry

---

## 🔗 Live Demo

[View the live app on Render](https://fitness-club-jfd8.onrender.com)

> **Demo Credentials:**  
> Username: `admin`  
> Password: `Mabutsi@12`  

---

## 🛠️ Features

### 1. User Management
- Secure login/logout system for staff
- Admin role-based access control
- Default admin account auto-created on first run
- Session management for secure access

### 2. Members
- Add, edit, delete member profiles
- Membership types: Monthly, Quarterly, Yearly, Custom
- Automatic membership expiry tracking
- Phone number and contact management
- Membership status monitoring

### 3. Trainers & Classes
- Complete trainer profile management
- Add, edit, delete gym classes with schedules
- Track upcoming and today's classes
- Assign trainers to specific classes
- Class capacity and attendance tracking

### 4. Payments
- Record and track payments per member
- Payment history with timestamps
- Monthly revenue tracking and reporting
- Sample payments generator for testing and demo

### 5. Check-ins
- Daily check-in tracking for active members
- Weekly and monthly check-in statistics
- Prevent duplicate check-ins per day per member
- Automatic cleanup of orphaned check-in records

### 6. Dashboard
- Comprehensive overview: total members, active memberships, trainers, classes
- Revenue analytics and financial reporting
- Most popular class and busiest trainer insights
- Member satisfaction calculation based on engagement metrics
- SMS reminders simulation for membership expiry

### 7. API Endpoints (JSON)
- `/api/search_members?q=<name>` → Search members by name
- `/api/members_needing_reminders` → Members with expiring memberships
- `/api/members_with_phones` → Members with phone numbers for communications
- `/send_reminder/<member_id>` → Send simulated SMS reminder to member

---
## 💻 Technologies Used

- **Backend:** Python, Flask, Flask-SQLAlchemy
- **Database:** SQLite (with PostgreSQL compatibility)
- **Frontend:** HTML, CSS, Jinja2 templates
- **Authentication:** Flask sessions with secure password hashing
- **Server:** Render (cloud hosting)
- **Libraries:** SQLAlchemy, datetime, collections, hashlib


