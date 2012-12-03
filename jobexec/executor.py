import urllib, urllib.request, urllib.error, urllib.parse, logging, zipfile, tarfile, tempfile, os, shutil, subprocess, signal, stat, configparser, sys, fcntl
from datetime import datetime

submit_server = None
secret = None		
targetdir=None
pidfile=None

# Send some result to the SUBMIT server
def send_result(msg, error_code, submission_file_id, action):
	logging.info("Test for submission file %s completed with error code %s: %s"%(submission_file_id, str(error_code), msg))
	if error_code==None:
		error_code=-9999	# avoid special case handling on server side
	post_data = [('SubmissionFileId',submission_file_id),('Message',msg),('ErrorCode',error_code),('Action',action)]    
	try:
		urllib.request.urlopen('%s/jobs/secret=%s'%(submit_server, secret), urllib.parse.urlencode(post_data))	
	except urllib.error.HTTPError as e:
		logging.error(str(e))
		exit(-1)

# Fetch any available work from the SUBMIT server
# returns job information from the server
def fetch_job():
	try:
		result = urllib.request.urlopen("%s/jobs/secret=%s"%(submit_server,secret))
		fname=targetdir+datetime.now().isoformat()
		headers=result.info()
		submid=headers['SubmissionFileId']
		action=headers['Action']
		timeout=int(headers['Timeout'])
		logging.info("Retrieved submission file %s for '%s' action: %s"%(submid, action, fname))
		if 'PostRunValidation' in headers:
			validator=headers['PostRunValidation']
			logging.debug("Using validator from "+validator)
		else:
			validator=None
		target=open(fname,"wb")
		target.write(result.read())
		target.close()
		return fname, submid, action, timeout, validator
	except urllib.error.HTTPError as e:
		if e.code == 404:
			logging.debug("Nothing to do.")
			exit(0)
		else:
			logging.error(str(e))
			exit(-1)

# Decompress the downloaded file into "targetdir"
# Returns on success, or terminates the executor after notifying the SUBMIT server
def unpack_job(fname, submid, action):
	# os.chroot is not working with tarfile support
	finalpath=targetdir+str(submid)+"/"
	shutil.rmtree(finalpath, ignore_errors=True)
	os.makedirs(finalpath)
	if zipfile.is_zipfile(fname):
		logging.debug("Valid ZIP file")
		f=zipfile.ZipFile(fname, 'r')
		logging.debug("Extracting ZIP file.")
		f.extractall(finalpath)
		os.remove(fname)
	elif tarfile.is_tarfile(fname):
		logging.debug("Valid TAR file")
		tar = tarfile.open(fname)
		logging.debug("Extracting TAR file.")
		tar.extractall(finalpath)
		tar.close()
		os.remove(fname)
	else:
		os.remove(fname)
		shutil.rmtree(finalpath, ignore_errors=True)
		send_result("This is not a valid compressed file.",-1, submid, action)
		exit(-1)		
	dircontent=os.listdir(finalpath)
	logging.debug("Content after decompression: "+str(dircontent))
	if len(dircontent)==0:
		send_result("Your compressed upload is empty - no files in there.",-1, submid, action)
	elif len(dircontent)==1 and os.path.isdir(finalpath+os.sep+dircontent[0]):
		logging.warning("The archive contains no Makefile on top level and only the directory %s. I assume I should go in there ..."%(dircontent[0]))
		finalpath=finalpath+os.sep+dircontent[0]
	return finalpath


# Signal handler for timeout implementation
def handle_alarm(signum, frame):
	# Needed for compatibility with both MacOS X and Linux
	if 'self' in frame.f_locals:
		pid=frame.f_locals['self'].pid
	else:
		pid=frame.f_back.f_locals['self'].pid
	logging.info("Got alarm signal, killing %s due to timeout."%(str(pid)))
	os.killpg(pid, signal.SIGTERM)

# Perform some execution activity, with timeout support
# This is used both for compilation and validator script execution
def run_job(finalpath, cmd, submid, action, timeout, keepdata=False):
	logging.debug("Changing to target directory.")
	os.chdir(finalpath)
	logging.debug("Installing signal handler for timeout")
	signal.signal(signal.SIGALRM, handle_alarm)
	logging.info("Spawning process for "+str(cmd))
	proc=subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
	logging.debug("Starting timeout counter: %u seconds"%timeout)
	signal.alarm(timeout)
	output=None
	stderr=None
	try:
		output, stderr = proc.communicate()
		logging.debug("Process terminated")
	except:
		logging.debug("Seems like the process got killed by the timeout handler")
	if output == None:
		output = ""
	else:
		output=output.decode("utf-8")
	if stderr == None:
		stderr = ""
	else:
		stderr=stderr.decode("utf-8")
	signal.alarm(0)
	if action=='test_compile':
		action_title='Compilation'
	elif action=='test_validity':
		action_title='Validation'
	elif action=='test_full':
		action_title='Testing'
	else:
		assert(False)
	if proc.returncode == 0:
		logging.info("Executed with error code 0: \n\n"+output)
		if not keepdata:
			shutil.rmtree(finalpath, ignore_errors=True)
		return output
	elif (proc.returncode == 0-signal.SIGTERM) or (proc.returncode == None):
		shutil.rmtree(finalpath, ignore_errors=True)
		send_result("%s was terminated since it took too long (%u seconds). Output so far:\n\n%s"%(action_title,timeout,output), proc.returncode, submid, action)
		exit(-1)		
	else:
		dircontent = subprocess.check_output(["ls","-ln"])
		dircontent = dircontent.decode("utf-8")
		output=output+"\n\nDirectory content as I see it:\n\n"+dircontent
		shutil.rmtree(finalpath, ignore_errors=True)
		send_result("%s was not successful:\n\n%s"%(action_title,output), proc.returncode, submid, action)
		exit(-1)		

# read configuration
config = configparser.RawConfigParser()
if len(sys.argv) > 1:
	config.read(sys.argv[1])
else:
	config.read("./executor.cfg")
# configure logging module
logformat=config.get("Logging","format")
logfile=config.get("Logging","file")
loglevel=logging._levelNames[config.get("Logging","level")]
logtofile=config.getboolean("Logging","to_file")
if logtofile:
	logging.basicConfig(format=logformat, level=loglevel, filename='/tmp/executor.log')
else:
	logging.basicConfig(format=logformat, level=loglevel)	
# set global variables
submit_server=config.get("Server","url")
secret=config.get("Server","secret")
targetdir=config.get("Execution","directory")
pidfile=config.get("Execution","pidfile")
assert(targetdir.startswith('/'))
assert(targetdir.endswith('/'))
script_runner=config.get("Execution","script_runner")
serialize=config.getboolean("Execution","serialize")

# If the configuration says when need to serialize, check this
if serialize:
	fp = open(pidfile, 'w')
	try:
		fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
		logging.debug("Got the script lock")
	except IOError:
		logging.debug("Script is already running.")
		exit(0)

# fetch any available job
fname, submid, action, timeout, validator=fetch_job()
# decompress download, only returns on success
finalpath=unpack_job(fname, submid, action)
# perform action defined by the server for this download
if action == 'test_compile':
	# build it, only returns on success
	output=run_job(finalpath,['make'],submid, action, timeout)
	send_result(output, 0, submid, action)
elif action == 'test_validity' or action == 'test_full':
	# build it, only returns on success
	run_job(finalpath,['make'],submid,action,timeout,keepdata=True)
	# fetch validator into target directory 
	logging.debug("Fetching validator script from "+validator)
	urllib.request.urlretrieve(validator, finalpath+"validator.py")
	os.chmod(finalpath+"validator.py", stat.S_IXUSR|stat.S_IRUSR)
	# Allow submission to load their own libraries
	logging.debug("Setting LD_LIBRARY_PATH to "+finalpath)
	os.environ['LD_LIBRARY_PATH']=finalpath
	# execute validator
	output=run_job(finalpath,[script_runner, 'validator.py'],submid,action,timeout)
	send_result(output, 0, submid, action)
else:
	# unknown action, programming error in the server
	assert(False)
