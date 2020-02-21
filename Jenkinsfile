pipeline {
    agent none
    stages {
        stage('Build') {
            agent any
            steps {
                echo 'Building..'
                //step([$class: 'DockerComposeBuilder', dockerComposeFile: 'docker-compose.yml', option: [$class: 'StartService', scale: 1, service: 'dev'], useCustomDockerComposeFile: true])
                //sh 'docker-compose -f docker-compose.yml -f dev.yml build dev'
            }
        }
        stage('Test') {
            agent any
            steps {
                echo 'Testing..'
            }
        }
        stage('Deploy') {
            agent any
            steps {
                echo 'Deploying....'
            }
        }
    }
}
