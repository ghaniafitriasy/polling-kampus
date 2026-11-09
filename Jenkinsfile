pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    triggers {
        // Dipicu oleh GitHub Webhook setiap ada git push
        githubPush()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Syntax Check') {
            steps {
                // Cek sintaks Python di dalam container (tidak perlu Python di Windows)
                bat 'docker run --rm -v "%CD%:/src" -w /src python:3.12-slim python -B -m py_compile app.py'
                // Cek docker-compose.yml valid
                bat 'docker compose config -q'
            }
        }

        stage('Build Image') {
            steps {
                bat 'docker compose build backend'
            }
        }

        stage('Automated Deployment') {
            steps {
                // --force-recreate: container dibuat ulang agar index.html dan nginx.conf
                // hasil checkout terbaru ikut terpakai. Data aman karena ada di named volume.
                bat 'docker compose up -d --force-recreate --remove-orphans'
            }
        }

        stage('Health Check') {
            steps {
                powershell '''
                    $ok = $false
                    for ($i = 1; $i -le 20; $i++) {
                        try {
                            Invoke-WebRequest -UseBasicParsing -Uri http://localhost:5000/health | Out-Null
                            Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8081/api/votes | Out-Null
                            Write-Host 'Health check OK: backend dan frontend merespons'
                            $ok = $true
                            break
                        } catch {
                            Write-Host "Menunggu aplikasi siap ($i/20)..."
                            Start-Sleep -Seconds 3
                        }
                    }
                    if (-not $ok) {
                        Write-Host 'Health check GAGAL'
                        docker compose ps
                        docker compose logs --tail=50
                        exit 1
                    }
                '''
            }
        }
    }

    post {
        success {
            echo 'Deploy berhasil: http://localhost:8081'
        }
        failure {
            echo 'Pipeline gagal. Lihat log stage yang berwarna merah.'
        }
    }
}