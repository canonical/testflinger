import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from sanity.agent.data import dev_data


class mail:
    # mail
    MESSG = ["finished", "failed"]
    PASSWD = "ectgbttmpfsbxxrg"
    fromaddr = "an.wu@canonical.com"
    recipients = ["oem-sanity@lists.canonical.com", "an.wu@canonical.com"]

    def send_mail(status="failed", message="None", filename=""):
        msg = MIMEMultipart()
        msg["From"] = mail.fromaddr
        msg["To"] = ", ".join(mail.recipients)
        msg["Subject"] = "{} Auto Sanity was {} !!".format(
            dev_data.project, mail.MESSG[status]
        )
        body = "This is auto sanity bot notification\n" + message
        msg.attach(MIMEText(body, "plain"))

        if filename != "":
            filename = filename
            attachment = open(filename, "rb")
            p = MIMEBase("application", "octet-stream")
            p.set_payload((attachment).read())
            encoders.encode_base64(p)
            p.add_header(
                "Content-Disposition", "attachment; filename= %s" % filename
            )
            msg.attach(p)

        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(mail.fromaddr, mail.PASSWD)
        text = msg.as_string()
        s.sendmail(mail.fromaddr, mail.recipients, text)
        s.quit()
