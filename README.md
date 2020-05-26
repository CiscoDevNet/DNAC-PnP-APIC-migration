# APIC-EM PnP Migratiton to Cisco DNA Center
Some customers have been using the old workflow based PnP procecss in APIC-EM and wish to migrate to Cisco DNA Center

One challenge they have is using static config files.  This is often the case if another tool is generating the device configuration file

These scripts allow you to automate the upload of a set of config files into the template engine on DNAC (with no varaibles) 
and then use another script to do a site based claim (instead of a workflow based claim - as was the case in APIC-EM)

Site based claim is much simpler than workflow as the only way to create workdflows now is to use the API.  This process can be quite complex.

These scripts use the DNA Center SDK, but can be easily converted to raw REST API calls.

## Getting stated
First (optional) step, create a vitualenv. This makes it less likely to clash with other python libraries in future.
Once the virtualenv is created, need to activate it.
```buildoutcfg
python3 -m venv env3
source env3/bin/activate
```

Next clone the code.

```buildoutcfg
git clone https://github.com/CiscoDevNet/DNAC-XXX.git
```

Then install the  requirements (after upgrading pip). 
Older versions of pip may not install the requirements correctly.
```buildoutcfg
pip install -U pip
pip install -r requirements.txt
```

## Environment variables
The DNAC, username and passowrd of DNAC is specified in environment varaibles.  An example is provided in dnac_vars.
You can edit this file and use the "source" command to put the variables in your shell environment.
```buildoutcfg
source vars_dnac
```

## Load config files
This process assumes you have a mechanism for generating configuration files.  The 00load_config_files.py script will sync 
files in a given directory with the "Onbaording Configuration" folder in the DNA Center template editor.  In the 
example below, the configuration files are in "work_files/configs"

```buildoutcfg
$ ./00load_config_files.py --dir work_files/configs
Processing:switch1.cfg: adding NEW:Commiting e156e9e6-653d-4016-85bd-f142ba0659f8
Processing:switch3.cfg: adding NEW:Commiting 9ae1a187-422d-41b9-a363-aafa8724a5b2
```

If you were to re-run the script, it will check the hash of the uploaded file, and upload an updated version if required.

## Create Rules for devices
There is a sample csv file.  The main fields are name, serial, productId an siteName.  image is optional.

```buildoutcfg
$ cat work_files/devices.csv 
name,serial,pid,siteName,template,image
adam123,12345678902,c9300,Global/AUS/SYD5,switch1.cfg,cat3k_caa-universalk9.16.09.05.SPA.bin
adam124,12345678902,c9300,Global/AUS/SYD5,switch2.cfg,cat3k_caa-universalk9.16.09.05.SPA.bin
adam_bad_image,12345678902,c9300,Global/AUS/SYD5,switch2.cfg,cat3k_caa-universalk9.16.09.10.SPA.bin

```

## Adding devices 
The 10_add_and_claim.py script takes the work_files/devices.csv as an argumnent and add the device to DNA Center and
claims it to the required site.  The errors below are expected as it shows a missing configuration file and mission image.

```buildoutcfg
$ ./10_add_and_claim.py --file work_files/devices.csv 
Device:12345678902 name:adam123 siteName:Global/AUS/SYD5 Status:PLANNED
##ERROR adam124,12345678902: Cannot find template:switch2.cfg
##ERROR adam_bad_image,12345678902: Cannot find image:cat3k_caa-universalk9.16.09.10.SPA.bin

```

