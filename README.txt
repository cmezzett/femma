FEderation Metadata Manager for ADFS (femma) is a script that parses a 
(Shibboleth) federation metadata XML content and creates a pool
of metadata files and a powershell script in order to automatically
configure and update an Active Directory Federation Services
STS (Security Token Service).

Femma works on Python 2.5+ and depends on the lxml library.

Installation
------------
Femma is intended to be used on a Windows platform where the ADFSv2
service is installed. These packages have to be installed:
- python2.5:
  http://www.python.org/ftp/python/2.5/python-2.5.msi
- lxml library:
  http://pypi.python.org/packages/2.5/l/lxml/lxml-2.2.6.win32-py2.5.exe#md5=5824f195b457bb8b613d0369a54ccc70

Documentation
-------------
This script is intended to automate membership configuration of an ADFS
STS in a Shibboleth Federation. In fact ADFS is not able to handle
metadata with more than one EntityDescriptor element. A workaround to this
limit is to download the metadata, split it for each member, create the
associated ruleset file and generate a powershell script to be executed
in order to import metadata and apply the associated ruleset.

First of all, customize the context-based variables at the beginning of settings.cfg:
- idpEntityID: your identity provider entityID
- myClaimType: namespace for issued claims by the custom rules
- fedNamePrefix: a short name of your federation, every Relying Party Trust in
                 ADFS will be prefixed with this string
- myProxy: address of your proxy if femma can't access Internet directly to
           to update Federation metadata
- myProxyPort: port of your proxy if femma can't access Internet directly to
           to update Federation metadata

Modify the shipped update.bat script to match your configuration and execute it 
(as administrator). This batch file creates 2 directories, one with metadata files,
one with ruleset files and a powershell script (update_metadata_rptrust.ps1) that use
them in order to update your relying party trust configuration. You can create a scheduled
task to run it regularly to update RP trust in your federation. If you have more than one
STS you must install and configure femma and the scheduled task on each server, the
powershell script will detect if it's running on the primary server and exit otherwise.
The temporary directory and files are cleaned after the execution of the powershell script.

For your convenience is also included a little script (adfs2fed.py) that converts ADFS
metadata to a Shibboleth-friendly format, it can be used by you to submit updated metadata
or by your federation technical staff to regularly update the metadata.

Configuration file
------------------
You can customize the settings.cfg in order to inform femma about which Service Provider
entityID have to be ignored (i.e. if there are configuration problem as certificate duplication).
To do that you have to uncomment [ExcludeEntityID] section and list your blacklisted
entityID as:
key1=http://example.com
key2=http://newexample.com

Femma already skips Service Providers that that do not support SAML2 or that do not provide
AssertionConsumerService via HTTPS protocol.

With settings.cfg you may also configure custom rule for selected Service Providers.
The rule must be provided in a rule file into the 'customRules' directory, with this naming
convention:
rule_rulename1.tpl
rule_rulename2.tpl

And in settings.cfg, uncomment the [ServiceProviderAttributes] section with this syntax:
SPentityID=rulename1,rulename2

Examples:
moodle-shib.unimore.it/sp=persistent,eppn,sn,givenName,mail
vconf.garr.it/shibboleth=persistent,givenName,mail,sn,rulename1

In the template directory are already provided some of the most common rules.

Known Bugs
----------
- Only service providers are managed
- Every time the powershell script is executed all federation relying party are
  deleted and then recreated (slow if the federation has many members)
- Ruleset templates are intended for use with the Italian IDEM Federation, you need
  to customize them to your needs
- xml signature is not verified
