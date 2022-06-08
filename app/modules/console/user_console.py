import datetime
import typing as t

from console import Console, FuncItem, COLOR_NAME
from console.formatter import create_menu_bg, create_line

from app.utilities.logger import logger
from app.utilities.utils import days_to_date, exec_command, count_connections
from app.utilities.validators import UserValidator

from app.domain.dtos import UserDto
from app.domain.use_cases import UserUseCase

from app.data.repositories import UserRepository
from .utils import UserMenuConsole

from .v2ray_utils import V2rayUtils
from .openvpn_utils import OpenVPNUtils


class UserInputData:
    def __init__(
        self,
        username: t.Optional[str] = None,
        password: t.Optional[str] = None,
        connection_limit: t.Optional[str] = None,
        expiration_date: t.Optional[str] = None,
        v2ray_uuid: t.Optional[str] = None,
    ):
        self._username = username
        self._password = password
        self._connection_limit = connection_limit
        self._expiration_date = expiration_date
        self._v2ray_uuid = v2ray_uuid

    @property
    def username(self):
        while not self._username:
            self._username = input(COLOR_NAME.YELLOW + 'Nome de usuário: ' + COLOR_NAME.RESET)
            if not UserValidator.validate_username(self._username):
                self._username = None

        return self._username

    @username.setter
    def username(self, value):
        if UserValidator.validate_username(value):
            self._username = value

    @property
    def password(self):
        while not self._password:
            self._password = input(COLOR_NAME.YELLOW + 'Senha: ' + COLOR_NAME.RESET)
            if not UserValidator.validate_password(self._password):
                self._password = None

        return self._password

    @password.setter
    def password(self, value):
        if UserValidator.validate_password(value):
            self._password = value

    @property
    def connection_limit(self):
        while not self._connection_limit:
            self._connection_limit = input(
                COLOR_NAME.YELLOW + 'Limite de conexões: ' + COLOR_NAME.RESET
            )
            if not UserValidator.validate_connection_limit(self._connection_limit):
                self._connection_limit = None

        return self._connection_limit

    @connection_limit.setter
    def connection_limit(self, value):
        if UserValidator.validate_connection_limit(value):
            self._connection_limit = value

    @property
    def expiration_date(self):
        while not self._expiration_date:
            self._expiration_date = input(
                COLOR_NAME.YELLOW + 'Data de expiração: ' + COLOR_NAME.RESET
            )
            if self._expiration_date.isdigit() and int(self._expiration_date) > 0:
                self._expiration_date = days_to_date(int(self._expiration_date))

            if not UserValidator.validate_expiration_date(self._expiration_date):
                self._expiration_date = None

        return self._expiration_date

    @expiration_date.setter
    def expiration_date(self, value):
        if UserValidator.validate_expiration_date(value):
            self._expiration_date = value

    @property
    def v2ray_uuid(self):
        while not self._v2ray_uuid and V2rayUtils.v2ray_is_installed():
            self._v2ray_uuid = input(
                COLOR_NAME.YELLOW + 'Você deseja criar um UUID? (s/n) ' + COLOR_NAME.RESET
            )
            if self._v2ray_uuid == 's':
                self._v2ray_uuid = V2rayUtils.create_uuid()
            else:
                self._v2ray_uuid = None

        return self._v2ray_uuid

    @v2ray_uuid.setter
    def v2ray_uuid(self, value):
        self._v2ray_uuid = value

    def to_dict(self):
        return {
            'username': self.username,
            'password': self.password,
            'connection_limit': self.connection_limit,
            'expiration_date': datetime.datetime.strptime(
                self.expiration_date,
                '%d/%m/%Y',
            ),
            'v2ray_uuid': self.v2ray_uuid,
        }

    @classmethod
    def of(cls, data: t.Dict[str, t.Any]) -> 'UserInputData':
        if not data or not isinstance(data, dict):
            raise ValueError('Dados não informados')

        return cls(
            username=data.get('username'),
            password=data.get('password'),
            connection_limit=data.get('connection_limit'),
            expiration_date=data.get('expiration_date'),
            v2ray_uuid=data.get('v2ray_uuid'),
        )


class UserManager:
    def __init__(self, user_input_data: UserInputData, user_use_case: UserUseCase):
        if not user_input_data or not isinstance(user_input_data, UserInputData):
            raise ValueError('UserInputData não informado')

        if not user_input_data.username:
            raise ValueError('Nome de usuário não informado')

        self._user_input_data = user_input_data
        self._user_use_case = user_use_case

    def create_user(self) -> t.Dict[str, t.Any]:
        user_dto = UserDto.of(self._user_input_data.to_dict())
        user = self._user_use_case.create(user_dto)
        return user.to_dict()

    def update_password(self, password: str = None) -> t.Dict[str, t.Any]:
        password = password or self._user_input_data.password
        user = self._user_use_case.get_by_username(self._user_input_data.username)

        user_dto = UserDto.of(user)
        user_dto.password = password

        data = self._user_use_case.update(user_dto)
        cmd = 'echo %s:%s | chpasswd' % (data['username'], data['password'])
        exec_command(cmd)
        return data.to_dict()

    def update_connection_limit(self, connection_limit: int) -> t.Dict[str, t.Any]:
        if isinstance(connection_limit, str) and not connection_limit.isdigit():
            raise ValueError('Limite de conexões deve conter apenas números')

        user = self._user_use_case.get_by_username(self._user_input_data.username)

        user_dto = UserDto.of(user)
        user_dto.connection_limit = connection_limit
        self._user_use_case.update(user_dto)
        return user_dto.to_dict()

    def update_expiration_date(
        self,
        expiration_date: t.Union[datetime.datetime, str],
    ) -> t.Dict[str, t.Any]:
        if isinstance(expiration_date, str) and len(expiration_date) == 10:
            expiration_date = datetime.datetime.strptime(expiration_date, '%d/%m/%Y')

        if isinstance(expiration_date, str) and len(expiration_date) == 19:
            expiration_date = datetime.datetime.strptime(expiration_date, '%Y-%m-%d %H:%M:%S')

        if not isinstance(expiration_date, datetime.datetime):
            raise ValueError('Data de expiração inválida')

        user = self._user_use_case.get_by_username(self._user_input_data.username)

        user_dto = UserDto.of(user)
        user_dto.expiration_date = expiration_date
        self._user_use_case.update(user_dto)

        expiration_date = expiration_date.strftime('%Y-%m-%d')
        cmd_set_expiration_date = 'usermod --expiry %s %s' % (user.username, expiration_date)
        exec_command(cmd_set_expiration_date)
        return user_dto.to_dict()

    def delete_user(self) -> t.Dict[str, t.Any]:
        user = self._user_use_case.get_by_username(self._user_input_data.username)
        self._user_use_case.delete(user.id)

        cmd = 'userdel --force %s' % user.username
        exec_command(cmd)

        return user.to_dict()

    @staticmethod
    def show_message_user_created(user: t.Dict[str, t.Any]):
        Console.clear_screen()

        line = create_menu_bg('Usuário criado com sucesso!')
        line += '\n'
        line += COLOR_NAME.YELLOW + 'Nome de usuário: ' + COLOR_NAME.RESET + user['username'] + '\n'
        line += COLOR_NAME.YELLOW + 'Senha: ' + COLOR_NAME.RESET + user['password'] + '\n'
        line += (
            COLOR_NAME.YELLOW
            + 'Limite de conexões: '
            + COLOR_NAME.RESET
            + str(user['connection_limit'])
            + '\n'
        )
        line += (
            COLOR_NAME.YELLOW
            + 'Data de expiração: '
            + COLOR_NAME.RESET
            + user['expiration_date'].strftime('%d/%m/%Y')
            + '\n'
        )

        if user['v2ray_uuid']:
            line += (
                COLOR_NAME.YELLOW + 'UUID do V2Ray: ' + COLOR_NAME.RESET + user['v2ray_uuid'] + '\n'
            )

        if user.get('ovpn_path') and user.get('ovpn_path').startswith('/'):
            line += (
                COLOR_NAME.YELLOW + 'Arquivo OVPN: ' + COLOR_NAME.RESET + user['ovpn_path'] + '\n'
            )

        print(line)


class UserMenuConsoleDeleteUser(UserMenuConsole):
    def __init__(self, user_use_case: UserUseCase, callback_select_user: t.Callable):
        super().__init__(user_use_case)
        self._callback_select_user = callback_select_user

    def select_user(self, user: t.Dict[str, t.Any]) -> None:
        self._user_selected = user
        self._callback_select_user(user)
        self.create_items()


class UserMenuConsolePassword(UserMenuConsole):
    def create_items(self) -> None:
        self._console.items.clear()

        if not self._users:
            logger.error('Nenhum usuario foi encontrado.')
            self._console.pause()
            return

        for user in self._users:
            user_dto = UserDto.of(user)
            self._console.append_item(
                FuncItem(
                    user['username'].ljust(self.width()) + ' - ' + user['password'],
                    self.select_user,
                    user_dto.to_dict(),
                )
            )


class UserMenuConsoleConnectionLimit(UserMenuConsole):
    def create_items(self) -> None:
        self._console.items.clear()

        if not self._users:
            logger.error('Nenhum usuario foi encontrado.')
            self._console.pause()
            return

        for user in self._users:
            user_dto = UserDto.of(user)
            self._console.append_item(
                FuncItem(
                    user['username'].ljust(self.width()) + ' - %02d' % user['connection_limit'],
                    self.select_user,
                    user_dto.to_dict(),
                )
            )


class UserMenuConsoleExpirationDate(UserMenuConsole):
    def create_items(self) -> None:
        self._console.items.clear()

        if not self._users:
            logger.error('Nenhum usuario foi encontrado.')
            self._console.pause()
            return

        for user in self._users:
            user_dto = UserDto.of(user)
            self._console.append_item(
                FuncItem(
                    user['username'].ljust(self.width())
                    + ' - '
                    + user['expiration_date'].strftime('%d/%m/%Y'),
                    self.select_user,
                    user_dto.to_dict(),
                )
            )


class UserAction:
    @staticmethod
    def create_user_action(user_input_data: UserInputData):
        Console.clear_screen()
        print(create_menu_bg('CRIAR USUARIO', set_pars=False))

        user_manager = UserManager(user_input_data, UserUseCase(UserRepository()))

        try:
            data = user_manager.create_user()

            if OpenVPNUtils.openvpn_is_installed():
                result = input('Deseja gerar ovpn para o usuário? [S/N] ')
                if result.lower() == 's':
                    path = OpenVPNUtils.create_ovpn_client(data['username'])
                    data['ovpn_path'] = path

            user_manager.show_message_user_created(data)
        except Exception as e:
            logger.error(e)

        Console.pause()

    @staticmethod
    def delete_user_action(user_data: t.Dict[str, t.Any]):
        if not user_data:
            return

        try:
            user_manager = UserManager(UserInputData.of(user_data), UserUseCase(UserRepository()))
            user_manager.delete_user()
            logger.info('Usuário deletado com sucesso.')
        except Exception as e:
            logger.error(e)

        Console.pause()

    @staticmethod
    def password_change_action(user_data: t.Dict[str, t.Any]) -> None:
        if not user_data:
            return

        logger.info('Usurário: %s', COLOR_NAME.YELLOW + user_data['username'] + COLOR_NAME.RESET)
        logger.info('Senha atual: %s', COLOR_NAME.YELLOW + user_data['password'] + COLOR_NAME.RESET)

        try:
            user_manager = UserManager(UserInputData.of(user_data), UserUseCase(UserRepository()))
            user_manager.update_password(UserInputData().password)
            logger.info('Senha alterada com sucesso!')
        except Exception as e:
            logger.error(e)

        Console.pause()

    @staticmethod
    def limit_connection_change_action(user_data: t.Dict[str, t.Any]) -> None:
        if not user_data:
            return

        logger.info('Usurário: %s', COLOR_NAME.YELLOW + user_data['username'] + COLOR_NAME.RESET)
        logger.info(
            'Limite atual: %s',
            COLOR_NAME.YELLOW + str(user_data['connection_limit']) + COLOR_NAME.RESET,
        )

        try:
            user_manager = UserManager(UserInputData.of(user_data), UserUseCase(UserRepository()))
            user_manager.update_connection_limit(UserInputData().connection_limit)
            logger.info('Limite de conexões alterado com sucesso!')
        except Exception as e:
            logger.error(e)

        Console.pause()

    @staticmethod
    def expiration_date_change_action(user_data: t.Dict[str, t.Any]) -> None:
        if not user_data:
            return

        user_dto = UserDto.of(user_data)
        expiration_date = user_dto.expiration_date

        if isinstance(user_dto.expiration_date, str):
            expiration_date = datetime.datetime.strptime(
                user_dto.expiration_date,
                '%Y-%m-%d %H:%M:%S',
            )

        days_to_expiration = (expiration_date - datetime.datetime.now()).days

        logger.info('Usurário: %s', COLOR_NAME.YELLOW + user_data['username'] + COLOR_NAME.RESET)
        logger.info(
            'Data atual: %s',
            COLOR_NAME.YELLOW + expiration_date.strftime('%d/%m/%Y') + COLOR_NAME.RESET,
        )
        logger.info(
            'Dias restantes: %s',
            COLOR_NAME.YELLOW + str(days_to_expiration) + COLOR_NAME.RESET,
        )

        try:
            user_manager = UserManager(UserInputData.of(user_data), UserUseCase(UserRepository()))
            user_input = UserInputData()

            new_date_expiration = datetime.datetime.strptime(user_input.expiration_date, '%d/%m/%Y')
            user_manager.update_expiration_date(new_date_expiration)

            logger.info(
                'Data de expiração alterada com sucesso! %s -> %s',
                expiration_date,
                new_date_expiration,
            )
        except Exception as e:
            logger.error(e)

        Console.pause()

    @staticmethod
    def monitor_action() -> None:
        users = UserUseCase(UserRepository()).get_all()

        if not users:
            logger.error('Nenhum usuario foi encontrado.')
            Console.pause()
            return

        width = max(len(user['username']) for user in users)
        width_username = width if width > 7 else 7

        message = (
            create_menu_bg(
                (
                    ' | '.join(
                        [
                            'USUARIO'.ljust(width),
                            'LIMITE DE CONEXÕES'.ljust(width),
                            'DATA DE EXPIRACAO'.ljust(width),
                        ]
                    )
                ),
                set_pars=False,
            )
            + '\n'
        )

        for user in users:
            user_dto = UserDto.of(user)

            count = count_connections(user_dto.username)

            message += ' {} | {} | {}\n'.format(
                COLOR_NAME.GREEN + user_dto.username.ljust(width_username) + COLOR_NAME.RESET,
                str(
                    '%s%02d/%s%02d%s'
                    % (
                        COLOR_NAME.GREEN,
                        user_dto.connection_limit,
                        COLOR_NAME.GREEN if count > 0 else COLOR_NAME.RED,
                        count,
                        COLOR_NAME.RESET,
                    )
                )
                .rjust(30)
                .ljust(36),
                '%s%s%s'
                % (
                    COLOR_NAME.GREEN,
                    user_dto.expiration_date.strftime('%d/%m/%Y').rjust(15),
                    COLOR_NAME.RESET,
                ),
            )

            message += create_line(show=False) + '\n'

        Console.clear_screen()
        print(message)
        Console.pause()


def user_console_main():
    console = Console('GERENCIADOR DE USUÁRIOS')
    console.append_item(
        FuncItem(
            'CRIAR USUÁRIO',
            lambda: UserAction.create_user_action(UserInputData()),
        )
    )
    console.append_item(
        FuncItem(
            'DELETAR USUÁRIO',
            lambda: UserMenuConsoleDeleteUser(
                UserUseCase(UserRepository()), UserAction.delete_user_action
            ).show(),
        )
    )
    console.append_item(
        FuncItem(
            'ALTERAR SENHA',
            lambda: UserAction.password_change_action(
                UserMenuConsolePassword(UserUseCase(UserRepository())).show()
            ),
        )
    )
    console.append_item(
        FuncItem(
            'ALTERAR LIMITE',
            lambda: UserAction.limit_connection_change_action(
                UserMenuConsoleConnectionLimit(UserUseCase(UserRepository())).show()
            ),
        )
    )
    console.append_item(
        FuncItem(
            'ALTERAR EXPIRACAO',
            lambda: UserAction.expiration_date_change_action(
                UserMenuConsoleExpirationDate(UserUseCase(UserRepository())).show()
            ),
        )
    )
    console.append_item(
        FuncItem(
            'MONITOR',
            lambda: UserAction.monitor_action(),
        )
    )
    console.show()
