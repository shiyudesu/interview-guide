ALTER TABLE interview_sessions
    ADD COLUMN request_id VARCHAR(64);

CREATE UNIQUE INDEX uk_interview_sessions_request_id
    ON interview_sessions (request_id);
