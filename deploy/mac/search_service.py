"""Keep the managed search container available after user login/Docker restart."""
import subprocess,time

def run(*args):
    return subprocess.run(args,capture_output=True,text=True,timeout=20)

last_open=0
last_state=None
while True:
    try:
        healthy=run('/usr/local/bin/docker','info','--format','{{.ServerVersion}}').returncode==0
        if not healthy:
            if time.monotonic()-last_open>60:
                run('/usr/bin/open','-g','-a','Docker');last_open=time.monotonic()
            state='waiting-for-docker'
        else:
            container=run('/usr/local/bin/docker','inspect','--format','{{.State.Running}}','crawl-search-searxng')
            if container.returncode:state='container-missing-run-installer'
            elif container.stdout.strip()=='true':state='running'
            else:
                started=run('/usr/local/bin/docker','start','crawl-search-searxng')
                state='starting' if started.returncode==0 else 'container-start-failed'
    except (OSError,subprocess.TimeoutExpired) as exc:state=type(exc).__name__
    if state!=last_state:print(state,flush=True);last_state=state
    time.sleep(15)
