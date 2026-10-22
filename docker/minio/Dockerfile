FROM golang:1.24-bookworm AS builder

ENV CGO_ENABLED=0 \
    GOMAXPROCS=2

RUN go install -p 2 \
    github.com/minio/minio@RELEASE.2025-09-07T16-13-09Z

FROM debian:bookworm-slim

COPY --from=builder /go/bin/minio /usr/local/bin/minio
COPY --from=builder /etc/ssl/certs/ca-certificates.crt \
    /etc/ssl/certs/ca-certificates.crt

EXPOSE 9000 9001

ENTRYPOINT ["/usr/local/bin/minio"]