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
from string import Template

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

    d = dict(
        bgcolor = colors[category],
        category = category,
        name = name,
        output = '<br/>'.join(out),
        tag = conf.email_subject_tag,
        sender = conf.email_sender,
        receivers = conf.email_receivers
    )

    tpl = open('.supcut/email.tpl').read()
    tpl = Template(tpl)
    html = tpl.safe_substitute(d)

    # Record the MIME type
    part = MIMEText(html, 'html')

    # Attach parts into message container.
    msg.attach(part)

    # adding icon
    from email.MIMEImage import MIMEImage

    image = open('/usr/share/pixmaps/faces/penguin.jpg', 'rb').read()
    image = MIMEImage(image)
    image.add_header('Content-ID', '<image1>')
    msg.attach(image)

    try:
        session = SMTP(conf.email_server)
        session.sendmail(conf.email_sender, conf.email_receivers, msg.as_string())
        session.close()
    except Exception,  e:
        print("Unable to deliver email: %s", e)

