# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS builder

WORKDIR /build
COPY go/go.mod go/go.sum ./
RUN go mod download

COPY go/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o northwind-delivery ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app
COPY --from=builder /build/northwind-delivery .

EXPOSE 8000
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["/app/northwind-delivery", "-healthcheck"]

USER nonroot:nonroot
ENTRYPOINT ["/app/northwind-delivery"]
