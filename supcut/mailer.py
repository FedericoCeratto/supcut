#
# supcut - Simple Unobtrusive Python Contituous Unit Testing
#
# Copyright (C) 2010 Federico Ceratto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

colors = {
    'success': '#eeffee',
    'failure': '#ffeeee'
}

def send_email(conf, category, name, out):
    """Send HTML formatted email"""
    if not conf.email_server:
        return

    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "%s %s: %s " % (conf.email_subject_tag, category, name)
    msg['From'] = conf.email_sender
    msg['To'] = conf.email_receivers
    
    background = colors[category]

    html = """
<html>
  <style>
    div {
        background-color: """ + background + """;
        border: 1px solid #bbbbb;
        padding: 0.2em;
        width: 40%;
        margin: 1em;
    }
    div p {
        font-size: 110%;
        padding-left: 1em;
    }
    </style>
  <body>
    <p>Automated email from Supcut</p>
    <div><p>""" + category + ":" + name + """</p><div>
    <p>""" + '</br>'.join(out) + """</p>
  </body>
</html>
"""

    # Record the MIME type
    part = MIMEText(html, 'html')

    # Attach parts into message container.
    msg.attach(part)

    try:
        session = SMTP(conf.email_server)
        session.sendmail(conf.email_sender, conf.email_receivers, msg.as_string())
        session.close()
    except Exception,  e:
        print("Unable to deliver email: %s", e)

