from drupalGitSSHDaemon import *
from twisted.cred.credentials import UsernamePassword, SSHPrivateKey
import random
import unittest

class StubMeta(DrupalMeta):
    """Avoid making the calls out to Drupal for some tests."""
    def __init__(self, keys, passwords):
        self.valid_keys = keys
        self.valid_passwords = passwords

    def request(self, value, var="user"):
        if var == "user":
            return {"keys":self.valid_keys, "password":None, "repos":[]}
        elif var == "fingerprint":
            return ["test.git"]

    def repopath(self, username, reponame, argv):
        pass

    def pubkeys(self, username):
        return self.valid_keys

    def passwords(self, username):
        return self.valid_passwords

class TestPubKeyAuth(unittest.TestCase):
    user = 'test'
    fingerprint = 'e4d3b1a13c247635a4f4b9fcd1d39298'
    blob = """ssh-dss AAAAB3NzaC1kc3MAAACBAN7d2tP4glvVqiKwV+55/U/pRrr1mcs2L15dBG5bYAbev3aN3dj/6upwd1IlCSnnWGuTPzAOQYEjDCRBTMYnduZappVM6PGTVywFIzFuupmGUbZI6S4JKxuMfGFegfnAjE0OakK9oBYtNsNqdS+19nj+oZC6T4Ogp5IJ4vo8f03pAAAAFQC/yGTGz+eLZwD6zJ+P87pxwlf5oQAAAIEAuk6n9xW6eUIloO0tKDchKBAjm7bZVmHzsWSfi7kG5/gfCeq4C+UDVA4oOBSnQ7IFqMTju8H7Xo+f+mJJkKPC5ymy6tIHBO3vw4Nq0t6D3iV4RRci/T7OP5pEq63MpQwUpseWraYb3xz/Qi/PLUvuVMsFdCiWIsJ1MqRKhm7ONNAAAACBAI8ycjnUcqiyvJMkaAZ+SpTG+rvnl/jzD8TvUizOODJWwX90mUY6PhLt0tGK4i6zjxHuVgQ1dkh3ldYd+4iM8zlOEMEA/SVTj4IuO9QhGkt7kdbCC1RvDQ2UGSV8pWl6XwJt9aCk4Q5MXYO8HO8wIOZnvOvt2xbIU3/dKAeNFYO6 test@test"""
    bad_blob = """ssh-dss AAAAB3NzaC1kc3MAAACBAOsD7WxLruieczHv46el57qKweUJU3R9ECYEDFs799b4BxKnHeJ+UPzC6+BIWqBdJ3+WGMTCMlXpZy3BlcVNdYLRI+AGBmdPW1rQxo0F9xpakFo9h9LKfpKeZz4mWp7FCOgkBmFlvJS+j9GYB/FEOE9LDqx0O7gBdAepm9WOieavAAAAFQDg+VFpV3y0rJbiPvbxj9PGW918ywAAAIAcOlBMKYPdqumG7pdiZtrTYhtwrfulxDy/MOBCcxqyhwuf1hSZZD5xDGbLyI58PLq2asfme1zLU5BSn8TnJJz8ddf3TFFVSJHdE0txuPu8LIfU3DMH2IDa4P/iU0QXlgGIurYeydKklzQg6FeLI+mjqr6LaLhSyBh3bdqW9GCBDwAAAIAa+/R5Bi7u9u7nk+IrAkrUuZciR+HUERBKWLBlCgldSZouziRLq2SkKPEsED2zni80SQxVeIG84olrQlThh35iYsJFNwS4J9vxQ5AJzARMACFYK/EzuFkk2YPV0NfurKd1KUoU8cb+5ns+gwgqWy06/s8jr63cDKWJmm+Hn2RwkQ== demo@demo"""

    def setUp(self):
        self.meta = StubMeta([self.fingerprint], [])
        self.checker = GitPubKeyChecker(self.meta)

    def test_good_key(self):
        credentials = SSHPrivateKey(self.user, "dsa", self.blob, None, None)
        self.assertTrue(self.checker.checkKey(credentials))

    def test_bad_key(self):
        credentials = SSHPrivateKey(self.user, "dsa", self.bad_blob, None, None)
        self.assertFalse(self.checker.checkKey(credentials))

class TestPasswordAuth(unittest.TestCase):
    user = 'test'
    password = 'Thai1mil3ahb'
    password_hash = '3d6e6e70c75f60ccf3b0f57dff19aac6'

    def setUp(self):
        self.meta = StubMeta([], [self.password_hash])
        self.checker = GitPasswordChecker(self.meta)

    def test_good_password(self):
        success = defer.succeed(self.user)
        credentials = UsernamePassword(self.user, self.password)
        deferred = self.checker.requestAvatarId(credentials)
        self.assertEqual(type(deferred.result), type(success.result))

    def test_bad_password(self):
        failure = defer.fail(UnauthorizedLogin("invalid password"))
        credentials = UsernamePassword(self.user, "the wrong password")
        deferred = self.checker.requestAvatarId(credentials)
        self.assertEqual(deferred.result.type, failure.result.type)
        # Collect the unhandled but intentional errors
        defer.DeferredList([deferred, failure], consumeErrors=True)

if __name__ == '__main__':
    unittest.main()
