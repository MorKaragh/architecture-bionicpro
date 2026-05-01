CREATE USER IF NOT EXISTS reports
IDENTIFIED WITH plaintext_password BY 'reports_password';

GRANT SELECT, INSERT, CREATE, TRUNCATE ON reports.* TO reports;
