{{- define "echokey.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "echokey.selectorLabels" -}}
app.kubernetes.io/name: {{ include "echokey.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "echokey.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "echokey.labels" -}}
helm.sh/chart: {{ include "echokey.chart" . }}
{{ include "echokey.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "echokey.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}
