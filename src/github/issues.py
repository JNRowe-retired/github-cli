import sys
import webbrowser as browser
from optparse import OptionParser

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        print "error: simplejson required"
        sys.exit(1)

from github2.client import Github

from github.utils import  get_remote_info, edit_text, \
    get_remote_info_from_option, get_prog, Pager, wrap_text, get_underline, \
    get_config
from github.version import get_version


def smart_unicode(text):
    try:
        return str(text)
    except UnicodeEncodeError:
        return text.encode('utf-8')


def format_issue(issue, verbose=True):
    output = []
    if verbose:
        indent = ""
    else:
        indent = " " * (5 - len(str(issue.number)))
    title = "%s%s. %s" % (indent, issue.number, issue.title)
    title = smart_unicode(title)
    if not verbose:
        output.append(title[:80])
    if verbose:
        title = wrap_text(title)
        output.append(title)
        underline = get_underline(title)
        output.append(underline)
        if issue.body:
            body = smart_unicode(wrap_text(issue.body))
            output.append(body)
        output.append("    state: %s" % issue.state)
        output.append("     user: %s" % issue.user)
        output.append("    votes: %s" % issue.votes)
        output.append("  created: %s" % issue.created_at)
        updated = issue.updated_at
        if updated and not updated == issue.created_at:
            output.append("  updated: %s" % updated)
        output.append(" comments: %s" % issue.comments)
        output.append(" ")
    return output


def format_comment(comment, nr, total):
    timestamp = getattr(comment, "updated_at", comment.created_at)
    title = "comment %s of %s by %s (%s)" % (nr, total, comment.user,
        timestamp)
    title = smart_unicode(title)
    output = [title]
    underline = get_underline(title)
    output.append(underline)
    body = smart_unicode(wrap_text(comment.body))
    output.append(body)
    return output


def pprint_issue(issue, verbose=True):
    lines = format_issue(issue, verbose)
    lines.insert(0, " ") # insert empty first line
    print "\n".join(lines)


def handle_error(result):
    output = []
    for msg in result['error']:
        if msg == result['error'][0]:
            output.append(msg['error'])
        else:
            output.append("error: %s" % msg['error'])
    error_msg = "\n".join(output)
    raise Exception(error_msg)


def validate_number(number, example):
    msg = "number required\nexample: %s" % example.replace("%prog", get_prog())
    if not number:
        raise Exception(msg)
    else:
        try:
            int(number)
        except:
            raise Exception(msg)


def get_key(data, key):
    try:
        return data[key]
    except KeyError:
        raise Exception("unexpected failure")


def create_edit_issue(issue=None, text=None):
    main_text = """# Please explain the issue.
# The first line will be used as the title.
# Lines starting with `#` will be ignored."""
    if issue:
        issue.main = main_text
        template = """%(title)s
%(body)s
%(main)s
#
#    number:  %(number)s
#      user:  %(user)s
#     votes:  %(votes)s
#     state:  %(state)s
#   created:  %(created_at)s""" % issue.__dict__
    else:
        template = "\n%s" % main_text
    if text:
        # \n on the command-line becomes \\n; undoing this:
        text = text.replace("\\n", "\n")
    else:
        text = edit_text(template)
        if not text:
            raise Exception("can not submit an empty issue")
    lines = text.splitlines()
    title = lines[0]
    body = "\n".join(lines[1:]).strip()
    return title, body


def create_comment(issue):
    inp = """
# Please enter a comment.
# Lines starting with `#` will be ignored.
#
#    number:  %(number)s
#      user:  %(user)s
#     votes:  %(votes)s
#     state:  %(state)s
#   created:  %(created_at)s""" % issue.__dict__
    out = edit_text(inp)
    if not out:
        raise Exception("can not submit an empty comment")
    lines = out.splitlines()
    comment = "\n".join(lines).strip()
    return comment


class Commands(object):

    def __init__(self, github, user, repo):
        self.github = github
        self.user = user
        self.repo = repo
        self.url_template = "http://github.com/api/v2/json/issues/%s/%s/%s"

    def search(self, term=None, state='open', verbose=False, **kwargs):
        if not term:
            example = "%s search experimental" % get_prog()
            msg = "error: search term required\nexample: %s" % example
            print msg
            sys.exit(1)
        issues = self.__submit("search", term, state)
        header = "# searching for '%s' returned %s issues" % (term, len(issues))
        printer = Pager()
        printer.write(header)
        for issue in issues:
            lines = format_issue(issue, verbose)
            printer.write("\n".join(lines))
        printer.close()

    def list(self, state='open', verbose=False, webbrowser=False, **kwargs):
        if webbrowser:
            issues_url_template = "http://github.com/%s/%s/issues/%s"
            if state == "closed":
                issues_url = issues_url_template % (self.user, self.repo,
                    state)
            else:
                issues_url = issues_url_template % (self.user, self.repo, "")
            try:
                browser.open(issues_url)
            except:
                print "error: opening page in web browser failed"
            else:
                sys.exit(0)

        if state == 'all':
            states = ['open', 'closed']
        else:
            states = [state]
        printer = Pager()
        for st in states:
            header = "# %s issues on %s/%s" % (st, self.user, self.repo)
            printer.write(header)
            issues = self.__submit("list", st)
            if issues:
                for issue in issues:
                    lines = format_issue(issue, verbose)
                    printer.write("\n".join(lines))
            else:
                printer.write("no %s issues available" % st)
            if not st == states[-1]:
                printer.write() # new line between states
        printer.close()

    def show(self, number=None, verbose=False, webbrowser=False, **kwargs):
        validate_number(number, example="%prog show 1")
        if webbrowser:
            issue_url_template = "http://github.com/%s/%s/issues/%s/find"
            issue_url = issue_url_template % (self.user, self.repo, number)
            try:
                browser.open(issue_url)
            except:
                print "error: opening page in web browser failed"
            else:
                sys.exit(0)

        issue = self.__get_issue(number)
        if not verbose:
            pprint_issue(issue)
        else:
            printer = Pager()
            lines = format_issue(issue, verbose=True)
            lines.insert(0, " ")
            printer.write("\n".join(lines))
            if issue.comments > 0:
                comments = self.__submit("comments", number)
                lines = [] # reset
                total = len(comments)
                for i in range(total):
                    comment = comments[i]
                    lines.extend(format_comment(comment, i+1, total))
                    lines.append(" ")
                printer.write("\n".join(lines))
            printer.close()

    def open(self, message=None, **kwargs):
        title, body = create_edit_issue(text=message)
        issue = self.__submit("open", title, body)
        pprint_issue(issue)

    def close(self, number=None, **kwargs):
        validate_number(number, example="%prog close 1")
        issue = self.__submit("close", number)
        pprint_issue(issue)

    def reopen(self, number=None, **kwargs):
        validate_number(number, example="%prog open 1")
        result = self.__submit('reopen', number)
        issue = get_key(result, 'issue')
        pprint_issue(issue)

    def edit(self, number=None, **kwargs):
        validate_number(number, example="%prog edit 1")
        gh_issue = self.__get_issue(number)
        title, body = create_edit_issue(gh_issue)
        if title == gh_issue.title and \
                body == gh_issue.body.splitlines():
            print "no changes found"
            sys.exit(1)
        issue = self.__submit('edit', number, title, body)
        pprint_issue(issue)

    def label(self, command, label, number=None, **kwargs):
        validate_number(number, example="%prog label %s %s 1" % (command,
            label))
        if command not in ['add', 'remove']:
            msg = "label command should use either 'add' or 'remove'\n"\
                "example: %prog label add %s %s" % (label, number)
            raise Exception(msg)
        labels = self.__submit("%s_label" % command, number, label)
        if labels:
            print "labels for issue #%s:" % number
            for label in labels:
                print "- %s" % label
        else:
            print "no labels found for issue #%s" % number

    def comment(self, number=None, **kwargs):
        validate_number(number, example="%prog comment 1")
        gh_issue = self.__get_issue(number)
        comment = create_comment(gh_issue)
        returned_comment = self.__submit('comment', number, comment)
        if returned_comment:
            print "comment for issue #%s submitted successfully" % number

    def __get_issue(self, number):
        return self.__submit("show", number)

    def __submit(self, action, *args, **kwargs):
        project = "/".join([self.user, self.repo])
        return getattr(self.github.issues, action)(project, *args, **kwargs)


def main():
    usage = """usage: %prog command [args] [options]

Examples:
%prog list [-s open|closed|all]       show open, closed or all issues
                                    (default: open)
%prog [-s o|c|a] -v                   same as above, but with issue details
%prog                                 same as: %prog list
%prog -v                              same as: %prog list -v
%prog [-s o|c] -w                     show issues' GitHub page in web browser
                                    (default: open)
%prog show <nr>                       show issue <nr>
%prog show <nr> -v                    same as above, but with comments
%prog <nr>                            same as: %prog show <nr>
%prog <nr> -w                         show issue <nr>'s GitHub page in web
                                    browser
%prog open (o)                        create a new issue (with $EDITOR)
%prog open (o) -m <msg>               create a new issue with <msg> content 
                                    (optionally, use \\n for new lines; first 
                                    line will be the issue title)
%prog close (c) <nr>                  close issue <nr>
%prog open (o) <nr>                   reopen issue <nr>
%prog edit (e) <nr>                   edit issue <nr> (with $EDITOR)
%prog label add (al) <label> <nr>     add <label> to issue <nr>
%prog label remove (rl) <label> <nr>  remove <label> from issue <nr>
%prog search (s) <term>               search for <term> (default: open)
%prog s <term> [-s o|c] -v            same as above, but with details
%prog s <term> -s closed              only search in closed issues
%prog comment (m) <nr>                create a comment for issue <nr>
                                    (with $EDITOR)
%prog -r <user>/<repo>                specify a repository (can be used for
                                    all commands)
%prog -r <repo>                       specify a repository (gets user from
                                    global git config)
%prog -c <cache>                      specify a directory to cache HTTP data"""

    description = """Description:
command-line interface to GitHub's Issues API (v2)"""

    parser = OptionParser(usage=usage, description=description)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
      default=False, help="show issue details (only for show, list and "\
        "search commands) [default: False]")
    parser.add_option("-s", "--state", action="store", dest="state",
        type='choice', choices=['o', 'open', 'c', 'closed', 'a', 'all'],
        default='open', help="specify state (only for list and search "\
        "(except `all`) commands) choices are: open (o), closed (c), all "\
        "(a) [default: open]")
    parser.add_option("-m", "--message", action="store", dest="message",
      default=None, help="message content for opening an issue without "\
        "using the editor")
    parser.add_option("-r", "--repo", "--repository", action="store",
        dest="repo", help="specify a repository (format: "\
            "`user/repo` or just `repo` (latter will get the user from the "\
            "global git config))")
    parser.add_option("-w", "--web", "--webbrowser", action="store_true",
        dest="webbrowser", default=False, help="show issue(s) GitHub page "\
        "in web browser (only for list and show commands) [default: False]")
    parser.add_option("-c", "--cache", action="store", default=None,
        help="specify a directory to cache HTTP data")
    parser.add_option("-V", "--version", action="store_true",
        dest="show_version", default=False,
        help="show program's version number and exit")

    class CustomValues:
        pass
    (options, args) = parser.parse_args(values=CustomValues)

    kwargs = dict([(k, v) for k, v in options.__dict__.items() \
        if not k.startswith("__")])
    if kwargs.get('show_version'):
        print("ghi %s" % get_version('short'))
        sys.exit(0)

    if kwargs.get('state'):
        kwargs['state'] = {'o': 'open', 'c': 'closed', 'a': 'all'}.get(
            kwargs['state'], kwargs['state'])

    if args:
        cmd = args[0]
        try:
            nr = str(int(cmd))
            if cmd == nr:
                cmd = 'show'
                args = (cmd, nr)
        except:
            pass
    else:
        cmd = 'list' # default command

    if cmd == 'search':
        term = " ".join(args[1:])
        args = (args[0], term)

    # handle command aliases
    cmd = {'o': 'open', 'c': 'close', 'e': 'edit', 'm': 'comment',
        's': 'search'}.get(cmd, cmd)
    if cmd == 'open' and len(args) > 1:
        cmd = 'reopen'
    if cmd == 'al' or cmd == 'rl':
        alias = cmd
        cmd = 'label'
        args_list = [cmd, {'a': 'add', 'r': 'remove'}[alias[0]]]
        args_list.extend(args[1:])
        args = tuple(args_list)


    config = get_config()
    github = Github(username=config["user"], api_token=config["token"],
        cache=kwargs.get("cache"))
    try:
        repository = kwargs.get('repo')
        if repository:
            user, repo = get_remote_info_from_option(repository)
        else:
            user, repo = get_remote_info()

        commands = Commands(github, user, repo)
        getattr(commands, cmd)(*args[1:], **kwargs)
    except AttributeError:
        return "error: command '%s' not implemented" % cmd
    except Exception, info:
        return "error: %s" % info

if __name__ == '__main__':
    main()
