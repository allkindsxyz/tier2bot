#!/bin/bash

# Сохраняем текущий .env как .env.prod
if [ -f ".env" ]; then
  cp .env .env.prod
  echo "Текущий .env сохранен как .env.prod"
else
  echo "Файл .env не найден"
fi 