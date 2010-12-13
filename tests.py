from drupalGitSSHDaemon import *
from twisted.cred.credentials import UsernamePassword
import random
import unittest

class StubMeta(DrupalMeta):
    """Avoid making the calls out to Drupal for some tests."""
    def __init__(self, keys, passwords):
        self.valid_keys = keys
        self.valid_passwords = passwords

    def repopath(self, username, reponame, argv):
        pass

    def pubkeys(self, username):
        return self.valid_keys

    def passwords(self, username):
        return self.valid_passwords

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
