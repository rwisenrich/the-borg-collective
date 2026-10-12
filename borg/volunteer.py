"""Consent-first donation client. Runs approved inference only, never remote code.

A volunteer controls duration, job budget and CPU threads. Operators must
create a one-time/admission capability out of band in the current prototype.
"""
import os
import time
from . import client


def limits(threads=1,max_minutes=30,max_jobs=10,max_ram_mb=None):
    count=os.cpu_count() or 1
    if not isinstance(threads,int) or not 1<=threads<=count:
        raise ValueError('CPU-thread donation must be between 1 and your local CPU count')
    if not isinstance(max_minutes,int) or not 1<=max_minutes<=1440:
        raise ValueError('Donation time must be 1-1440 minutes')
    if not isinstance(max_jobs,int) or not 1<=max_jobs<=10000:
        raise ValueError('Donation job limit must be 1-10000')
    if max_ram_mb is not None and (not isinstance(max_ram_mb,int) or not 256<=max_ram_mb<=1048576):
        raise ValueError('Maximum RAM must be 256-1048576 MB')
    return {'threads':threads,'max_minutes':max_minutes,'max_jobs':max_jobs,
            'max_ram_mb':max_ram_mb,'observed_cpus':count}


def donate(url,identity_path,admission_token,backend='gguf',model=None,base_url=None,
           threads=1,max_minutes=30,max_jobs=10,max_ram_mb=None,gpu_layers=0,consent=False):
    if consent is not True:
        raise PermissionError('Volunteer must explicitly agree to the donation session')
    profile=limits(threads,max_minutes,max_jobs,max_ram_mb)
    if not isinstance(gpu_layers,int) or not 0<=gpu_layers<=200:
        raise ValueError('Bad GPU layer donation')
    if backend not in ('gguf','ollama','http-api','openai-compatible'):
        raise ValueError('Volunteer must use a real, explicitly selected inference backend')
    # Only local inference is recommended for actual donated compute; an
    # externally billed API would NOT donate hardware and may incur charges.
    if backend!='gguf':
        raise ValueError('Donation requires local GGUF weights in this release')
    if not admission_token:
        raise ValueError('Volunteer enrollment requires explicit network admission')
    os.environ['BORG_CPU_THREADS']=str(threads)
    os.environ['BORG_GPU_LAYERS']=str(gpu_layers)
    if max_ram_mb is not None:
        try:
            import resource
        except ImportError as exc:
            raise RuntimeError('RAM address-space limits unavailable on this OS') from exc
        cap=max_ram_mb*1024*1024
        soft,hard=resource.getrlimit(resource.RLIMIT_AS)
        if hard!=-1 and cap>hard:cap=hard
        resource.setrlimit(resource.RLIMIT_AS,(cap,hard))
    client.node_join(url,identity_path,admission_token,trusted=False)
    deadline=time.monotonic()+max_minutes*60
    n=0
    while n<max_jobs and time.monotonic()<deadline:
        try:
            done=client.work_once(url,identity_path,backend,model,base_url)
        except KeyboardInterrupt:
            break
        if done:n+=1
        else:time.sleep(min(2,max(0,deadline-time.monotonic())))
    return {'completed_jobs':n,'volunteer_stopped':True,'profile':profile}
