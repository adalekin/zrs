{{- define "zrs.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 50 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 50 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "zrs.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "zrs.selectorLabels" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "zrs.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- include "zrs.fullname" . -}}
{{- end -}}
{{- end -}}

{{- define "zrs.image" -}}
{{- printf "%s:%s" .image.repository (.image.tag | default .root.Chart.AppVersion) -}}
{{- end -}}

{{- define "zrs.imagePullSecrets" -}}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/* Environment of the server image: used by the server pods and by the migrations Job. */}}
{{- define "zrs.serverEnv" -}}
{{- $settings := .Values.settings -}}
- name: OIDC_ISSUER
  value: {{ required "settings.oidc.issuer is required" $settings.oidc.issuer | quote }}
- name: OIDC_AUDIENCE
  value: {{ required "settings.oidc.audience is required" $settings.oidc.audience | quote }}
- name: OIDC_ROLES_CLAIM
  value: {{ required "settings.oidc.rolesClaim is required" $settings.oidc.rolesClaim | quote }}
- name: ROLE_REQUESTER
  value: {{ required "settings.roles.requester is required" $settings.roles.requester | quote }}
- name: ROLE_MODERATOR
  value: {{ required "settings.roles.moderator is required" $settings.roles.moderator | quote }}
- name: ROLE_FINANCE_DIRECTOR
  value: {{ required "settings.roles.financeDirector is required" $settings.roles.financeDirector | quote }}
- name: ROLE_PAYER
  value: {{ required "settings.roles.payer is required" $settings.roles.payer | quote }}
- name: CURRENCIES
  value: {{ required "settings.currencies is required" ($settings.currencies | join ",") | quote }}
- name: ATTACHMENT_MAX_BYTES
  value: {{ required "settings.attachmentMaxBytes is required" $settings.attachmentMaxBytes | quote }}
- name: S3_ENDPOINT_URL
  value: {{ required "settings.storage.endpointUrl is required" $settings.storage.endpointUrl | quote }}
- name: S3_BUCKET
  value: {{ required "settings.storage.bucket is required" $settings.storage.bucket | quote }}
- name: S3_REGION
  value: {{ required "settings.storage.region is required" $settings.storage.region | quote }}
- name: S3_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "zrs.secretName" . }}
      key: S3_ACCESS_KEY_ID
- name: S3_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "zrs.secretName" . }}
      key: S3_SECRET_ACCESS_KEY
- name: DB_HOST
  value: {{ required "settings.database.host is required" $settings.database.host | quote }}
- name: DB_PORT
  value: {{ required "settings.database.port is required" $settings.database.port | quote }}
- name: DB_NAME
  value: {{ required "settings.database.name is required" $settings.database.name | quote }}
- name: DB_USER
  value: {{ required "settings.database.user is required" $settings.database.user | quote }}
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "zrs.secretName" . }}
      key: DB_PASSWORD
{{- end -}}
