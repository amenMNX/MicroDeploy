import main 
	
def test_worker_main_exists():
	assert callable(main.main)
		
def test_worker_db_configuration_exists():
	assert main.DB_PARAMS["database"] == "devops"