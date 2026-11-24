# Языковые материалы

## Аннотация

Работа посвящена учёту товаров клиентов склада ответственного хранения. Построены модели процесса и данных, реализованы приёмка, подбор ячейки best fit, FIFO, резервирование, выдача и отмена заказа на Python и Java. Снимок Python сохраняется и восстанавливается в SQLite; Java работает в памяти. На контрольном наборе заказ на 60 коробок получает 40 из L1 и 20 из L2, остатки после выдачи составляют 0/30/10. Пройдены 40 автоматизированных тестов; сравнение 92 состояний в 15 общих сценариях подтвердило совпадение реализаций. Прототип предназначен для обучения и не поддерживает параллельную работу склада.

## Abstract

This work studies inventory accounting for a third-party warehouse. Process and data models support two implementations, in Python and Java, of receiving, best-fit location selection, FIFO allocation, order reservation, dispatch and cancellation. A Python snapshot can be saved to and restored from SQLite; Java operates in memory. In the reference example, a 60-box order takes 40 boxes from L1 and 20 from L2, leaving lot balances of 0, 30 and 10. All 40 automated tests passed. Comparing 92 states across 15 shared scenarios confirmed matching results. The prototype is intended for education and does not support concurrent warehouse operations.

## Заключение

Получен воспроизводимый учебный прототип склада с двумя реализациями предметных правил, физической моделью данных и проверками. На общем наборе подтверждены порядок FIFO, раздельный учёт владельцев, атомарность проверенных отказов и запрет повторной выдачи. Сохранение SQLite восстанавливает партии, заказы, планы и журнал. Следующее направление развития — серверная транзакционная обработка и управление доступом; внедрение и экономический эффект не оценивались.

## Conclusion

The result is a reproducible educational warehouse prototype with two implementations of the business rules, a physical data model and automated checks. Shared scenarios confirm FIFO ordering, inventory separation by owner, atomic rejection of the tested invalid operations and prevention of duplicate dispatch. SQLite persistence restores lots, orders, allocation plans and the movement log. Future work may add server-side transactional processing and access control. Deployment and economic benefits have not been evaluated.

## Глоссарий

| Русский термин | English term | Значение / Meaning |
|---|---|---|
| Ответственное хранение | Third-party storage | Хранение товаров клиента / Storage of a client's goods |
| Ячейка хранения | Storage location | Место с ограниченной вместимостью / A location with limited capacity |
| Партия | Lot | Прослеживаемая группа товара / A traceable group of goods |
| Владелец товара | Inventory owner | Клиент, которому принадлежит товар / The client who owns the goods |
| Физический остаток | On-hand quantity | Количество на складе / Quantity physically held |
| Доступный остаток | Available stock | Незаблокированный остаток за вычетом резерва / Unblocked on-hand stock minus reservations |
| Резервирование | Reservation | Закрепление количества за заказом / Allocation of quantity to an order |
| Выдача заказа | Order dispatch | Списание по действующему резерву / Deduction against an active reservation |
| Первым поступил первым выдан | First in first out | Подбор по моменту приёмки / Allocation by receipt instant |
| Подбор минимальной достаточной ячейки | Best fit | Минимум свободного места после размещения / Minimum remaining free capacity |
| Инвариант | Invariant | Условие согласованности состояния / A condition of state consistency |
| Атомарность | Atomicity | Применение всей операции или отказ / Applying the entire operation or rejecting it |
| Внешний ключ | Foreign key | Ссылка на существующую связанную строку / A reference to an existing related row |
| Журнал движений | Movement log | История приходов и расходов / A record of receipts and dispatches |
| Снимок состояния | State snapshot | Представление всех учётных данных / A representation of all accounting data |

## Oral presentation

Good afternoon. My project concerns inventory accounting for a third-party warehouse. The main challenge is to keep each client's stock separate while receiving and dispatching goods.

I modelled the receiving, storage and dispatch process and designed a data model with eight entities. I implemented the warehouse rules twice: procedurally in Python and with classes and strategy interfaces in Java. Best fit selects the smallest suitable location. FIFO selects unblocked lots of the correct owner and product by receipt time, using a sequence number to break ties.

An order is reserved only when every line can be fulfilled. Dispatch checks the entire plan before changing quantities. Cancellation releases the reservation. A SQLite module saves and restores the Python state as one transaction. Java uses the same input files and operates in memory.

In the reference example, an order for sixty boxes takes forty boxes from the first lot and twenty from the second. The remaining lot quantities are zero, thirty and ten. All forty automated tests passed. Python and Java produced identical results for ninety-two states in fifteen shared scenarios.

The system is an educational prototype for one warehouse. It has no concurrent users, access control, expiry-date handling or production integration. Future work may add server-side transactions and a user interface. Thank you.
