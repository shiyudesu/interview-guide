FROM scratch

ARG SOURCE_REPOSITORY
ARG SOURCE_REVISION

LABEL org.opencontainers.image.description="InterviewGuide server-side pull deployment bundle" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.source="${SOURCE_REPOSITORY}" \
      org.opencontainers.image.title="InterviewGuide deployment bundle"

COPY compose.yml /bundle/compose.yml
COPY .env.example /bundle/.env.example
COPY install.sh /bundle/install.sh
COPY lib.sh /bundle/lib.sh
COPY refresh.sh /bundle/refresh.sh
COPY rollback.sh /bundle/rollback.sh
COPY status.sh /bundle/status.sh
COPY stop.sh /bundle/stop.sh
COPY update.sh /bundle/update.sh
COPY systemd/interview-guide-update.service.in /bundle/systemd/interview-guide-update.service.in
COPY systemd/interview-guide-update.timer /bundle/systemd/interview-guide-update.timer

CMD ["/bundle/update.sh"]
