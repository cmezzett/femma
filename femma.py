#!/usr/bin/env python
#
# Name: FEderation Metadata Manager for ADFS (FEMMA)
# Version: 0.4
# Author: Cristian Mezzetti <cristian.mezzetti@unibo.it>
# Home-page: http://sourceforge.net/projects/femma
# License: GNU GPL v2
# Description: This script parses a (Shibboleth) federation 
#              metadata XML content and creates a pool of 
#              metadata files and a powershell script in order
#              to automatically configure and update an Active
#              Directory Federation Services STS (Security Token Service).
#
# Copyright (C) 2010  Cristian Mezzetti
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.


from lxml import etree
import urllib2, os, sys, getopt, string, ConfigParser, re, shutil
from string import Template

settingsFile = "settings.cfg"
xmlDir = os.getcwd() + os.sep + "entities-temp"
rulesetDir = os.getcwd() + os.sep + "ruleset-temp"
templateDir = os.getcwd() + os.sep + "templates"
rulesetBaseTemplate = templateDir + os.sep + "ruleset_base.tpl"
rulesetPersistentTemplate = templateDir + os.sep + "ruleset_persistent.tpl"
rulesetTransientTemplate = templateDir + os.sep + "ruleset_transient.tpl"
pshTemplate = templateDir + os.sep + "powershell_metadata_update.tpl"
pshBaseTemplate = templateDir + os.sep + "powershell_base.tpl"
rulePrefix = "rule_"
rulesDir = templateDir
customRulesDir = templateDir + os.sep + "customRules"
ps1FileName = os.getcwd() + os.sep + "update_adfs_rptrust.ps1"

IDPSSO_DESC = '{urn:oasis:names:tc:SAML:2.0:metadata}IDPSSODescriptor'
SPSSO_DESC = '{urn:oasis:names:tc:SAML:2.0:metadata}SPSSODescriptor'
ENTITY_DESC = '{urn:oasis:names:tc:SAML:2.0:metadata}EntityDescriptor'

idpEntityID = ""
spEntityID = ""
myClaimType = ""
fedNamePrefix = ""
myProxy = ""

def tearUp():
	"""
	Initializes temp directories and checks for configuration settings
	"""
	global idpEntityID, spEntityID, myClaimType, fedNamePrefix, myProxy
	
	if os.path.exists(templateDir) and os.path.exists(settingsFile):
		config = ConfigParser.ConfigParser()
		config.read(settingsFile)
		idpEntityID = config.get('Settings', "idpEntityID")
		spEntityID = config.get('Settings', "spEntityID")
		myClaimType = config.get('Settings', "myClaimType")
		fedNamePrefix = config.get('Settings', "fedNamePrefix")
		myProxy = config.get('Settings', "myProxy")
		if myProxy.__len__() > 0:
			myProxy = myProxy + ":" + config.get('Settings', "myProxyPort")

		if not (os.path.exists(xmlDir) and os.path.isdir(xmlDir)):
			os.mkdir(xmlDir)
		if not (os.path.exists(rulesetDir) and os.path.isdir(rulesetDir)):
			os.mkdir(rulesetDir)
	else:
		print "ERROR: FEMMA configuration files not found"
		sys.exit(1)


def cleanUp():
	"""
	Cleans up temporary folders
	"""
	shutil.rmtree(xmlDir, True)
	shutil.rmtree(rulesetDir, True)
	try:
		os.unlink(ps1FileName)
		os.unlink('ProxyHTTPConnection.pyc')
	except:
		pass
	sys.exit(0)

def isPersistent(entityID):
	"""
	Checks if the provided entityID of the Service Provider has configured rules
	that match a list of sensitive ones. If this is the case, it associates a persistent-id.
	Default is transient-id.
	To customize this behavior, use the following section and syntax in settings.cfg:
	[SensitiveAttributes]
	rules = rule1,rule2

	To force the persistent NameID format, specify "persistent" in the SP attribute list
	"""
	ret = False
	# strips protocol identifier
	entityName = entityID.split('://')[1]
	
	config = ConfigParser.ConfigParser()
	config.read(settingsFile)
	try:
		sensitiveRules = config.get('SensitiveAttributes', 'rules')
		configuredRules = config.get('ServiceProviderAttributes', entityName)
		for r in sensitiveRules.split(','):
			if r in configuredRules.split(','):
				ret = True
				break
	except Exception, e:
		pass

	return ret

def rulesetCreation(myClaimType, rulesetFileName, spEntityID):
	"""
	Creates Service Provider ruleset file with NameID creation based on persistent-id by default
	"""
	try:
		# load template from configured file
		ruleBase = open(rulesetBaseTemplate, "r").read()
		if isPersistent(spEntityID) == True:
			ruleID = Template(open(rulesetPersistentTemplate, "r").read())
		else:
			ruleID = Template(open(rulesetTransientTemplate, "r").read())
		# susbstitutes rules and entityID
		outRuleset = ruleBase + "\n" + ruleID.substitute(claimBaseType=myClaimType, spNameQualifier=spEntityID, nameQualifier=idpEntityID)
		# create ruleset files
		rulesetFile = open(rulesetFileName, "w")
		rulesetFile.write(outRuleset)
		rulesetFile.write(getRules(spEntityID))
		rulesetFile.close()
	except Exception, e:
		print(e)
	return

def entityToIgnore(entityID):
	"""
	Checks if the provided entityID of the Service Provider is blacklisted
	To blacklist an entity ID insert a section into the settings file, with
	similar syntax:
	[ExcludeEntityID]
	entity1 = "https://my.example.com/service"
	entity2 = "https://anotherexample.net/service2"
	"""
	config = ConfigParser.ConfigParser()
	config.read(settingsFile)
	toIgnore = config.items('ExcludeEntityID')

	if entityID in [x[1] for x in toIgnore]:
		return True
	else:
		return False

def stripRolloverKeys(entity):
	"""
	If the entity metadata contains keys for safe-rollover, strips the Standby key because ADFS can't handle it
	"""
	toRemove = []
	for i in entity.iterdescendants('{http://www.w3.org/2000/09/xmldsig#}KeyName'):
		if i.text == "Standby":
			toRemove.append(i.getparent().getparent())

	for j in toRemove:
		parent = j.getparent()
		parent.remove(j)
		print "WARNING: removed KeyName element used for safe-rollover (ADFS can't handle it): " + entity.attrib['entityID']
		
	return entity

def stripBindingsNotSupported(entity):
	"""
	Removes AssertionConsumerService and SingleLogoutService not supported 
	by ADFS. Also removes AssertionConsumerService without HTTPS endpoint.
	Returns the modified entity or None if there aren't HTTPS endpoint after
	filtering
	"""
	bindingsNotSupported = ( \
	'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Artifact', \
	'urn:oasis:names:tc:SAML:2.0:bindings:SOAP', \
	'urn:oasis:names:tc:SAML:2.0:bindings:PAOS', \
	'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST-SimpleSign', \
	'urn:oasis:names:tc:SAML:1.0:profiles:browser-post', \
	'urn:oasis:names:tc:SAML:1.0:profiles:artifact-01')
	
	ACS = '{urn:oasis:names:tc:SAML:2.0:metadata}AssertionConsumerService'
	SLO = '{urn:oasis:names:tc:SAML:2.0:metadata}SingleLogoutService'

	spDescriptor = entity.find(SPSSO_DESC)
	
	for i in spDescriptor.iterchildren():
		if i.tag == ACS or i.tag == SLO:
			if (i.attrib['Binding'] in bindingsNotSupported) or \
			(not i.attrib['Location'].startswith('https')):
				spDescriptor.remove(i)

	if spDescriptor.findall(ACS).__len__() > 0:
		return entity
	else:
		print "WARNING: Skipping SP entityID because no HTTPS endpoint are provided " + entity.attrib['entityID']
		return None

def getRules(entityID):
	"""
	Checks if the provided entityID of the Service Provider needs additional rules other than the default ones.
	Every name in the list identifies a rule template (i.e.: eppn => rule_eppn.tpl). 
	The entity ID name must be stripped of the protocol prefix (http://, https://)
	Example configuration settings:
	[ServiceProviderAttributes]
	my.example.com/service=eppn,o,ou
	anotherexample.net/service2=carLicense
	"""
	ret = ""

	# strips protocol identifier
	entityName = entityID.split('://')[1]

	config = ConfigParser.ConfigParser()
	config.read(settingsFile)
	try:
		rules = config.get('ServiceProviderAttributes', entityName)
		for r in rules.split(','):
			ruleFileName = rulePrefix + r + '.tpl'
			if os.path.exists(rulesDir + os.sep + ruleFileName):
				ruleFile = open(rulesDir + os.sep + ruleFileName, 'r')
			else:
				ruleFile = open(customRulesDir + os.sep + ruleFileName, 'r')
			ret += ruleFile.read()
			ruleFile.close()
	except Exception, e:
		pass

	return ret


def getMetadataAsString(mdUrl, proxy):
	if proxy != "" and mdUrl.split('://')[0] != 'http':
		from ProxyHTTPConnection import ConnectHTTPSHandler
		opener = urllib2.build_opener(ConnectHTTPSHandler)
		urllib2.install_opener(opener)
		req = urllib2.Request(mdUrl)
		req.set_proxy(proxy, 'https')
		md = urllib2.urlopen(req)
	else:
		md = urllib2.urlopen(mdUrl)
	mdString = md.read()
	# use CRLF instead of LF
	mdString = re.sub("\r?\n", "\r\n", mdString)
	return etree.fromstring(mdString)


def metadataExtraction(mdUrl, xmlDir, proxy):
	"""
	Creates a metadata file for each entityID in Federation EntitiesDescriptor
	"""
	try:
		pshScript = ""
		pshScriptTemplate = Template(open(pshTemplate, 'r').read())
		fedMetadata = getMetadataAsString(mdUrl, proxy)
		# for each EntityDescriptor extracts SP and write a single metadata file
		for entity in fedMetadata.findall(ENTITY_DESC):
			spDescriptor = entity.find(SPSSO_DESC)
			if (spDescriptor is None):
				print "WARNING: Skipping entityID because it's not a Service Provider: " + entity.attrib['entityID']
				continue

			attribute = spDescriptor.get('protocolSupportEnumeration')
			# checkss if the SP do support SAML2
			if string.find(attribute, 'urn:oasis:names:tc:SAML:2.0:protocol') == -1:
				print "WARNING: Skipping SP entityID because SAML1 is not supported: " + entity.attrib['entityID']
				continue

			if entityToIgnore(entity.attrib['entityID']):
				print "INFO: Skipping SP entityID because it's blacklisted: " + entity.attrib['entityID']
				continue

			entity = stripBindingsNotSupported(entity)
			if entity is None:
				continue

			# creates a metadata file with only one EntityDescriptor for ADFS
			entity = stripRolloverKeys(entity)
			entities = fedMetadata
			entities.clear()
			entities.insert(0, entity)
			# filesystem-friendly name
			fname = entity.attrib['entityID'].replace('/', '_').replace('.', '_').replace(':', '_')
			fname = "".join([x for x in fname if x.isalpha() or x.isdigit() or x == '-' or x == '_'])
			entityFileName = xmlDir + os.sep + fname + ".xml"
			entityFile = open(entityFileName, "w")
			entityFile.write(etree.tostring(entities))
			entityFile.close()
			rulesetFileName = rulesetDir + os.sep + fname
			rulesetCreation(myClaimType, rulesetFileName, entity.attrib['entityID'])
			# append to the powershell script rules for this entityID
			pshScript += pshScriptTemplate.substitute(fedName=fedNamePrefix, metadataFile=entityFileName, rpName=entity.attrib['entityID'], rulesetFile=rulesetFileName)

		if pshScript:
			pshScriptBaseTemplate = Template(open(pshBaseTemplate, 'r').read())
			pshScript = pshScriptBaseTemplate.substitute(fedName=fedNamePrefix) + pshScript
			pshScriptFile = open(ps1FileName, 'w')
			pshScriptFile.write(pshScript)
			pshScriptFile.close()

	except Exception, e:
		print(e)
	return


def usage(ret=0):
	print "-h, --help"
	print "-t, --test"
	print "-m, --metadata:   URL of federation metadata"
	print "-x, --xmlsec:     path to xmlsec binary for signature verification"
	print "-c, --clean:      Clean up temporary folders" 
	sys.exit(ret)


def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "chtm:x:", ["clean", "help", "test", "metadata=", "xmlsec="])
	except getopt.GetoptError, err:
		print str(err)
		usage(2)

	mdUrl = ""
	if opts.__len__() != 0:
		for o, a in opts:
			if o in ("-x", "--xmlsec"):
				xmlsecbin = a
			elif o in ("-m", "--metadata"):
				tearUp()
				mdUrl = a
			elif o in ("-c", "--clean"):
				cleanUp()
			else:
				usage()
		# FIXME: add XML signature validation
		metadataExtraction(mdUrl, xmlDir, proxy=myProxy)
	else:
		usage()


if __name__ == "__main__":
	main()
