# Shared Session ID

## Usage

For apps that don't need to specifically start/end sessions, the shared session id will integrate into logs automatically.

To start or end a shared session, do the following:

```python
from mpetk.mpeconfig.python_3.session_id_db import start_session, end_session

start_session(time_to_live_s=60,kill_existing=False)

# Do stuff

end_session()
```

## Log Example

```
channel         app_session shared_session  level       message
---------------------------------------------------------------
sync	        c1ce063	    None        	START_STOP	Action, Stop, log_session, c1ce063, WinUserID, patrick.latimer,
sync	        c1ce063	    None        	INFO	    Sync log 19,
sync	        c1ce063	    None        	INFO	    Sync log 18,
mouse_director	4379fa6	    None        	START_STOP	Action, Stop, log_session, 4379fa6, WinUserID, patrick.latimer,
mouse_director	4379fa6	    None        	INFO	    one last log,
sync	        c1ce063	    None        	INFO	    Sync log 17,
sync	        c1ce063	    None        	INFO	    Sync log 16,
mouse_director	4379fa6	    acaffb1     	INFO	    Action, Ended shared session,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 15,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 14,
mouse_director	4379fa6	    acaffb1     	INFO	    Log 1,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 13,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 12,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 11,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 10,
mouse_director	4379fa6	    acaffb1     	START_STOP	Action, Start, log_session, 4379fa6, WinUserID, patrick.latimer,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 9,
mouse_director	e474cb0	    acaffb1     	START_STOP	Action, Stop, log_session, e474cb0, WinUserID, patrick.latimer,
mouse_director	e474cb0	    acaffb1     	INFO	    one last log,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 8,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 7,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 6,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 5,
mouse_director	e474cb0	    acaffb1     	INFO	    Log 1,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 4,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 3,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 2,
sync	        c1ce063	    acaffb1     	INFO	    Sync log 1,
mouse_director	e474cb0	    acaffb1     	INFO	    Action, Began shared session,
mouse_director	e474cb0	    None        	START_STOP	Action, Start, log_session, e474cb0, WinUserID, patrick.latimer,
sync	        c1ce063	    None        	INFO	    Sync log 0,
sync	        c1ce063	    None        	START_STOP	Action, Start, log_session, c1ce063, WinUserID, patrick.latimer,
```