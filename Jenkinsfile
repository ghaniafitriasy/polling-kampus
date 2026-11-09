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
                // Gagal bila ada salah tulis di kode Python atau di docker-compose.yml
                sh 'python3 -m py_compile app.py'
                sh 'docker compose config -q'
            }
        }

        stage('Build Image') {
            steps {
                sh 'docker compose build backend'
            }
        }

        stage('Automated Deployment') {
            steps {
                // --force-recreate: container dibuat ulang agar index.html dan nginx.conf
                // hasil checkout terbaru ikut terpakai. Data aman karena ada di named volume.
                sh 'docker compose up -d --force-recreate --remove-orphans'
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    for i in $(seq 1 20); do
                        if curl -fsS http://localhost:5000/health > /dev/null && \
                           curl -fsS http://localhost:8081/api/votes > /dev/null; then
                            echo "Health check OK: backend dan frontend merespons"
                            exit 0
                        fi
                        echo "Menunggu aplikasi siap ($i/20)..."
                        sleep 3
                    done
                    echo "Health check GAGAL"
                    docker compose ps
                    docker compose logs --tail=50
                    exit 1
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
