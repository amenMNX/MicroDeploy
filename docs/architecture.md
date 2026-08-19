\# Architecture



\## Components



\### API

FastAPI service that receives HTTP requests and writes tasks to PostgreSQL.



\### Worker

Background service that polls PostgreSQL and processes pending tasks.



\### Database

PostgreSQL database that stores tasks.



\## Local Flow



```text

User

&#x20; ↓

API Service

&#x20; ↓

PostgreSQL

&#x20; ↑

Worker Service

