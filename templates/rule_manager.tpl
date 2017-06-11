@RuleName = "manager"
c:[Type == "http://schemas.microsoft.com/ws/2008/06/identity/claims/windowsaccountname"] => add(store = "Active Directory", types = ("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/manager"), query = ";manager;{0}", param = c.Value);

@RuleName = "urn:mace:dir:attribute-def:manager"
c:[Type == "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/manager"] => issue(Type = "urn:mace:dir:attribute-def:manager", Value = c.Value, Properties["http://schemas.xmlsoap.org/ws/2005/05/identity/claimproperties/attributename"] = "urn:oasis:names:tc:SAML:2.0:attrname-format:uri");
