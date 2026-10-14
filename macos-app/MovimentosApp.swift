import SwiftUI
import Darwin

@main
struct MovimentosApp: App {
    var body: some Scene {
        // As ligações movimentos://… (botão «Fechar aplicação» da página) vão
        // para a janela já aberta, em vez de abrirem uma janela nova.
        WindowGroup {
            ContentView().handlesExternalEvents(preferring: ["*"], allowing: ["*"])
        }
        .handlesExternalEvents(matching: ["*"])
    }
}

// Onde corre o servidor (Docker/Colima com PostgreSQL + marimo).
enum Modo: String {
    case local    // neste Mac
    case remoto   // noutro Mac, por SSH (com túnel para o porto 2718)
}

// Estado de cada passo da 1.ª fase do encerramento (mostrado na janela da app).
enum Passo: Equatable {
    case emCurso
    case ok(String)
    case naoAplicavel(String)
    case falhou(String)
}

// Encerramento em duas fases, iniciado pelo botão «Fechar aplicação» da página:
//  1.ª fase (esta app): fechar o túnel SSH e confirmar que o porto ficou livre;
//  2.ª fase (utilizador): fechar a janela/separador do browser.
struct Encerramento {
    var tunel: Passo = .emCurso
    var porto: Passo = .emCurso
    // nil enquanto a 1.ª fase decorre; true/false quando termina
    var fase1Concluida: Bool? = nil
    // segundos até a app terminar sozinha (nil = sem contagem)
    var contagem: Int? = nil
}

// Arranca o servidor (Colima + docker compose, através do arrancar.sh do repo)
// e dá acesso à aplicação Marimo em http://localhost:2718:
//  - modo local:  diretamente;
//  - modo remoto: através de um túnel SSH.
final class Manager: ObservableObject {
    @Published var status = "Desligado"
    @Published var ocupado = false
    // Escolhido no arranque da app (nil = ainda não escolhido).
    @Published var modo: Modo? = nil
    // Último modo usado: fica como opção por omissão no arranque seguinte.
    @Published var ultimoModo: Modo
    @Published var destino: String { didSet { UserDefaults.standard.set(destino, forKey: "destino") } }
    @Published var repoDir: String { didSet { UserDefaults.standard.set(repoDir, forKey: "repoDir") } }
    @Published var repoLocal: String { didSet { UserDefaults.standard.set(repoLocal, forKey: "repoLocal") } }
    // Encerramento em curso (nil = não): a janela mostra o progresso da 1.ª fase.
    @Published var encerramento: Encerramento? = nil
    private var geracaoContagem = 0   // cancela a contagem decrescente
    private var portoPorLibertar: Int? = nil   // porto que ficou ocupado no último encerramento
    private var tunnel: Process?
    private var erroTunnel: Pipe?
    // Porto local do browser: no modo remoto pode não ser o 2718, se este Mac
    // também tiver o seu próprio servidor local (Colima) a ocupar esse porto.
    private var portaLocal = 2718
    private var geracao = 0   // muda a cada "Desligar": cancela esperas em curso
    private let porta = 2718
    private let opcoesSSH = ["-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                             "-o", "ServerAliveInterval=30"]

    init() {
        let d = UserDefaults.standard
        destino = d.string(forKey: "destino") ?? "postgres@mini-de-jose"
        repoDir = d.string(forKey: "repoDir") ?? "~/Public/BD"
        repoLocal = d.string(forKey: "repoLocal") ?? "~/Public/BD"
        ultimoModo = Modo(rawValue: d.string(forKey: "modo") ?? "") ?? .local
        // Túnel que tenha ficado aberto (a app terminou de forma anormal):
        // fechá-lo para libertar o porto 2718.
        let pidAntigo = d.integer(forKey: "pidTunnel")
        if pidAntigo > 0 { matarSeForSSH(pid_t(pidAntigo)) }
        d.removeObject(forKey: "pidTunnel")
    }

    private func matarSeForSSH(_ pid: pid_t) {
        let ps = Process()
        ps.executableURL = URL(fileURLWithPath: "/bin/ps")
        ps.arguments = ["-p", "\(pid)", "-o", "comm="]
        let saida = Pipe()
        ps.standardOutput = saida
        do { try ps.run() } catch { return }
        let nome = String(decoding: saida.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
        ps.waitUntilExit()
        if nome.trimmingCharacters(in: .whitespacesAndNewlines).hasSuffix("ssh") {
            kill(pid, SIGTERM)
        }
    }

    // Saída controlada (botão «Fechar aplicação» da página, link
    // movimentos://sair). 1.ª fase, mostrada passo a passo nesta janela, que
    // vem para a frente: fecha o túnel e confirma que o porto ficou livre.
    // Quando termina, a janela diz que pode fechar o browser (2.ª fase) e a
    // app termina sozinha ao fim de alguns segundos. No modo local o porto
    // 2718 é do próprio servidor, que continua a correr (backups, relatórios).
    func sair() {
        if let e = encerramento, e.fase1Concluida == nil { return }  // já em curso
        let t = tunnel
        // «Tentar de novo» depois de uma falha: o túnel já foi fechado, mas o
        // porto tem de ser verificado outra vez.
        let pendente = portoPorLibertar
        let porto = t != nil ? portaLocal : (pendente ?? portaLocal)
        let remoto = modo == .remoto
        geracaoContagem += 1
        encerramento = Encerramento()
        trazerParaAFrente()
        parar()
        DispatchQueue.global().async {
            // Passo 1: fechar o túnel SSH
            let passoTunel: Passo
            if let t = t {
                for _ in 0..<30 where t.isRunning { Thread.sleep(forTimeInterval: 0.1) }
                if t.isRunning { kill(t.processIdentifier, SIGKILL); t.waitUntilExit() }
                passoTunel = t.isRunning
                    ? .falhou("o túnel SSH não fechou (PID \(t.processIdentifier))")
                    : .ok("Túnel SSH fechado")
            } else if pendente != nil {
                passoTunel = .ok("Túnel SSH fechado")
            } else {
                passoTunel = .naoAplicavel(remoto
                    ? "Não havia nenhum túnel SSH aberto"
                    : "Modo local: não há túnel SSH")
            }
            DispatchQueue.main.async { self.encerramento?.tunel = passoTunel }

            // Passo 2: confirmar que o porto deste Mac ficou livre
            let passoPorto: Passo
            if !remoto {
                passoPorto = .naoAplicavel(
                    "O porto \(porto) pertence ao servidor local, que continua ativo (backups e relatórios)")
            } else if t == nil && pendente == nil {
                passoPorto = .naoAplicavel("O porto \(porto) não estava a ser usado por esta app")
            } else {
                Thread.sleep(forTimeInterval: 0.3)
                passoPorto = self.portaLivre(porto)
                    ? .ok("Porto \(porto) livre neste Mac")
                    : .falhou("O porto \(porto) continua ocupado — no Terminal: lsof -i :\(porto)")
            }
            DispatchQueue.main.async {
                if case .falhou = passoPorto { self.portoPorLibertar = porto }
                else { self.portoPorLibertar = nil }
                self.encerramento?.porto = passoPorto
                let falhou: Bool
                if case .falhou = passoTunel { falhou = true }
                else if case .falhou = passoPorto { falhou = true }
                else { falhou = false }
                self.encerramento?.fase1Concluida = !falhou
                self.status = falhou ? "Fase 1 do encerramento falhou ❌" : "Fase 1 concluída ✅"
                if !falhou { self.contarAteTerminar(10) }
                self.trazerParaAFrente()
            }
        }
    }

    // Contagem decrescente até terminar a app (cancelável com «Manter aberta»).
    private func contarAteTerminar(_ segundos: Int) {
        let g = geracaoContagem
        encerramento?.contagem = segundos
        if segundos <= 0 { NSApp.terminate(nil); return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            guard self.geracaoContagem == g, self.encerramento != nil else { return }
            self.contarAteTerminar(segundos - 1)
        }
    }

    // «Manter aberta»: cancela o encerramento e volta ao painel normal.
    func cancelarEncerramento() {
        geracaoContagem += 1
        encerramento = nil
    }

    // Mostra a janela da app à frente do browser, para se ver o progresso.
    private func trazerParaAFrente() {
        NSApp.activate(ignoringOtherApps: true)
        for w in NSApp.windows where w.canBecomeKey {
            if w.isMiniaturized { w.deminiaturize(nil) }
            w.makeKeyAndOrderFront(nil)
        }
    }

    func setStatus(_ s: String) { DispatchQueue.main.async { self.status = s } }
    private func setOcupado(_ b: Bool) { DispatchQueue.main.async { self.ocupado = b } }

    func escolher(_ m: Modo) {
        modo = m
        ultimoModo = m
        UserDefaults.standard.set(m.rawValue, forKey: "modo")
        status = m == .local ? "Servidor local (Colima neste Mac)" : "Desligado"
    }

    // Volta ao ecrã de escolha local/remoto.
    func mudarModo() {
        parar()
        modo = nil
    }

    // Corre um comando e devolve o código de saída e a última linha escrita
    // (para mostrar o erro no estado da app).
    private func correr(_ executavel: String, _ args: [String]) -> (Int32, String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: executavel)
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        p.environment = env
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do { try p.run() } catch { return (-1, error.localizedDescription) }
        let dados = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        let saida = String(decoding: dados, as: UTF8.self)
        let ultima = saida.split(whereSeparator: \.isNewline).last.map(String.init) ?? ""
        return (p.terminationStatus, ultima)
    }

    // Caminho para usar num comando de shell remoto (com ~ expandido no servidor).
    private func caminhoShell(_ p: String) -> String {
        func aspas(_ s: String) -> String { "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'" }
        if p == "~" { return "\"$HOME\"" }
        if p.hasPrefix("~/") { return "\"$HOME\"/" + aspas(String(p.dropFirst(2))) }
        return aspas(p)
    }

    // Arranca o Colima (se preciso) e os containers, neste Mac ou no servidor por SSH.
    func arrancarServidor() {
        guard let modo = modo else { return }
        ocupado = true
        status = modo == .local
            ? "A arrancar o Colima e os containers… (a 1.ª vez demora)"
            : "A arrancar o servidor remoto (Colima + docker compose)…"
        let repoLocal = (self.repoLocal as NSString).expandingTildeInPath
        let repoRemoto = repoDir.hasSuffix("/") ? String(repoDir.dropLast()) : repoDir
        let destino = self.destino
        DispatchQueue.global().async {
            let r: (Int32, String) = modo == .local
                ? self.correr("/bin/bash", [repoLocal + "/arrancar.sh"])
                : self.correr("/usr/bin/ssh", self.opcoesSSH +
                    [destino, "/bin/bash " + self.caminhoShell(repoRemoto + "/arrancar.sh")])
            if r.0 == 0 {
                self.setStatus(modo == .local
                    ? "Servidor ativo ✅ — clique em «Abrir no browser»"
                    : "Servidor ativo ✅ (\(destino)) — clique em «Ligar»")
            } else if modo == .remoto && r.0 == 255 {
                self.setStatus("Falha na ligação SSH ❌ — " + self.explicarErroSSH(r.1, destino))
            } else {
                self.setStatus("Falha ao arrancar ❌ — \(r.1.isEmpty ? "verifique o Colima" : r.1)")
            }
            self.setOcupado(false)
        }
    }

    // Modo remoto: cria o túnel SSH. Em ambos os modos, espera que a
    // aplicação responda e abre o browser.
    func ligar() {
        guard let modo = modo else { return }
        parar()
        let g = geracao
        let destino = self.destino
        if modo == .remoto {
            // 1.º porto livre a partir do 2718 (o 2718 pode estar ocupado pelo
            // servidor local deste Mac); no servidor remoto é sempre o 2718.
            guard let livre = (porta..<(porta + 20)).first(where: { portaLivre($0) }) else {
                setStatus("Não há nenhum porto livre entre \(porta) e \(porta + 19) ❌")
                return
            }
            portaLocal = livre
            setStatus("A ligar a \(destino)…")
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/ssh")
            p.arguments = opcoesSSH + ["-N", "-L", "\(livre):127.0.0.1:\(porta)", destino]
            let erro = Pipe()
            p.standardError = erro
            do {
                try p.run(); tunnel = p; erroTunnel = erro
                UserDefaults.standard.set(Int(p.processIdentifier), forKey: "pidTunnel")
            } catch {
                setStatus("Erro ao criar o túnel: \(error.localizedDescription)"); return
            }
        } else {
            portaLocal = porta
            setStatus("A aguardar a aplicação…")
        }
        DispatchQueue.global().async {
            for _ in 0..<60 {
                Thread.sleep(forTimeInterval: 1)
                if self.geracao != g { return }   // foi desligado entretanto
                if modo == .remoto, let t = self.tunnel, !t.isRunning {
                    let dados = self.erroTunnel?.fileHandleForReading.readDataToEndOfFile() ?? Data()
                    let texto = String(decoding: dados, as: UTF8.self)
                    self.setStatus("O túnel SSH falhou ❌ — " + self.explicarErroSSH(texto, destino))
                    return
                }
                if self.responde(self.portaLocal) {
                    let url = "http://localhost:\(self.portaLocal)"
                    self.setStatus(modo == .remoto ? "Ligado a \(destino) ✅ \(url)" : "Ligado ✅ \(url)")
                    DispatchQueue.main.async { NSWorkspace.shared.open(URL(string: url)!) }
                    return
                }
            }
            self.setStatus(modo == .remoto
                ? "A aplicação não respondeu em 60s ❌ — o servidor está a correr em \(destino)? (experimente «Arrancar servidor»)"
                : "A aplicação não respondeu em 60s ❌ (arrancou o servidor?)")
        }
    }

    func parar() {
        geracao += 1
        if let t = tunnel, t.isRunning {
            t.terminate()
            // se o ssh não sair a bem em 2 s, termina à força (liberta o porto)
            let pid = t.processIdentifier
            DispatchQueue.global().asyncAfter(deadline: .now() + 2) {
                if t.isRunning { kill(pid, SIGKILL) }
            }
        }
        tunnel = nil
        erroTunnel = nil
        UserDefaults.standard.removeObject(forKey: "pidTunnel")
        setStatus(modo == .local ? "Servidor local (Colima neste Mac)" : "Desligado")
    }

    // Verdadeiro se nenhum programa estiver a usar o porto neste Mac.
    private func portaLivre(_ p: Int) -> Bool {
        let s = socket(AF_INET, SOCK_STREAM, 0)
        if s < 0 { return false }
        defer { Darwin.close(s) }
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(UInt16(p).bigEndian)
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        // como o ssh: ignora ligações antigas em TIME_WAIT, só falha se
        // outro programa estiver mesmo à escuta no porto
        var um: Int32 = 1
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &um, socklen_t(MemoryLayout<Int32>.size))
        let r = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(s, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return r == 0 && !responde(p)
    }

    // Traduz os erros mais comuns do ssh numa indicação do que fazer.
    private func explicarErroSSH(_ texto: String, _ destino: String) -> String {
        let t = texto.lowercased()
        let ultima = texto.split(whereSeparator: \.isNewline).last.map(String.init) ?? "sem resposta do ssh"
        if t.contains("permission denied") {
            return "o SSH pede password, mas a app só entra com chave. No Terminal: ssh-copy-id \(destino)"
        }
        if t.contains("could not resolve hostname") {
            return "nome do servidor desconhecido (\(destino)). Experimente o nome com .local, p. ex. mini-de-jose.local"
        }
        if t.contains("host key verification failed") {
            return "chave do servidor ainda não aceite. No Terminal: ssh \(destino) (e responda yes)"
        }
        if t.contains("connection refused") {
            return "o servidor recusou a ligação: ative «Início de sessão remoto» nas Definições do Sistema dele"
        }
        if t.contains("timed out") || t.contains("no route to host") {
            return "o servidor não responde (desligado, a dormir ou noutra rede?)"
        }
        return ultima
    }

    private func responde(_ p: Int? = nil) -> Bool {
        let check = Process()
        check.executableURL = URL(fileURLWithPath: "/usr/bin/curl")
        check.arguments = ["-s", "-o", "/dev/null", "--max-time", "1", "http://127.0.0.1:\(p ?? porta)"]
        do { try check.run() } catch { return false }
        check.waitUntilExit()
        return check.terminationStatus == 0
    }
}

struct ContentView: View {
    @StateObject private var m = Manager()

    var body: some View {
        Group {
            if let e = m.encerramento {
                EncerramentoView(m: m, e: e)
            } else if let modo = m.modo {
                PainelView(m: m, modo: modo)
            } else {
                EscolhaView(m: m)
            }
        }
        .padding(24)
        .frame(minWidth: 480)
        // ao sair da app, fechar o túnel SSH (se existir)
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in
            m.parar()
        }
        // botão «Fechar aplicação» da página: movimentos://sair
        .onOpenURL { url in
            if url.scheme == "movimentos" && url.host == "sair" { m.sair() }
        }
    }
}

// Encerramento: progresso da 1.ª fase e indicação da 2.ª (fechar o browser).
struct EncerramentoView: View {
    @ObservedObject var m: Manager
    let e: Encerramento

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Movimentos · Arminda Melo RL").font(.headline)
                .frame(maxWidth: .infinity)
            Text("Encerramento da sessão").font(.title2).bold()

            Text("1.ª fase — fechar a ligação").font(.headline)
            linha(e.tunel)
            linha(e.porto)

            switch e.fase1Concluida {
            case nil:
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("A fechar a ligação…").foregroundStyle(.secondary)
                }
            case .some(true):
                Label("1.ª fase concluída", systemImage: "checkmark.seal.fill")
                    .font(.title3.bold())
                    .foregroundStyle(.green)
                Text("2.ª fase — feche agora a janela (ou o separador) do browser "
                     + "com a aplicação Movimentos.")
                    .font(.headline)
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    if let s = e.contagem {
                        Text("Esta app termina dentro de \(s) s.").foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Manter aberta") { m.cancelarEncerramento() }
                    Button("Terminar agora") { NSApp.terminate(nil) }
                        .keyboardShortcut(.defaultAction)
                }
            case .some(false):
                Label("A 1.ª fase não ficou concluída", systemImage: "exclamationmark.triangle.fill")
                    .font(.title3.bold())
                    .foregroundStyle(.red)
                Text("Não feche ainda o browser. Resolva o problema acima e carregue em "
                     + "«Tentar de novo», ou termine a app à mesma.")
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    Spacer()
                    Button("Voltar") { m.cancelarEncerramento() }
                    Button("Terminar à mesma") { NSApp.terminate(nil) }
                    Button("Tentar de novo") { m.sair() }.keyboardShortcut(.defaultAction)
                }
            }
        }
        .frame(minWidth: 460, alignment: .leading)
    }

    @ViewBuilder
    private func linha(_ p: Passo) -> some View {
        switch p {
        case .emCurso:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("…").foregroundStyle(.secondary)
            }
        case .ok(let t):
            Label(t, systemImage: "checkmark.circle.fill").foregroundStyle(.green)
        case .naoAplicavel(let t):
            Label(t, systemImage: "minus.circle").foregroundStyle(.secondary)
        case .falhou(let t):
            Label(t, systemImage: "xmark.circle.fill").foregroundStyle(.red)
        }
    }
}

// Ecrã inicial: escolher entre servidor local e servidor remoto.
struct EscolhaView: View {
    @ObservedObject var m: Manager

    var body: some View {
        VStack(spacing: 16) {
            Text("Movimentos · Arminda Melo RL").font(.headline)
            Text("Onde está o servidor?").foregroundStyle(.secondary)
            HStack(spacing: 16) {
                opcao(.local, "Servidor local", "desktopcomputer", "Colima neste Mac")
                opcao(.remoto, "Servidor remoto", "network", "Outro Mac, por SSH")
            }
        }
    }

    private func opcao(_ modo: Modo, _ titulo: String, _ icone: String, _ detalhe: String) -> some View {
        Button { m.escolher(modo) } label: {
            VStack(spacing: 6) {
                Image(systemName: icone).font(.system(size: 28))
                Text(titulo).bold()
                Text(detalhe).font(.caption).foregroundStyle(.secondary)
            }
            .frame(width: 170, height: 100)
        }
        .buttonStyle(CartaoStyle(destacado: m.ultimoModo == modo))
        // Enter escolhe o modo usado da última vez (destacado)
        .keyboardShortcut(m.ultimoModo == modo ? KeyboardShortcut.defaultAction : nil)
    }
}

// Botão grande em forma de cartão (os botões normais do macOS têm altura fixa).
struct CartaoStyle: ButtonStyle {
    var destacado: Bool

    func makeBody(configuration: Configuration) -> some View {
        let forma = RoundedRectangle(cornerRadius: 10)
        return configuration.label
            .padding(8)
            .background(forma.fill(Color.secondary.opacity(configuration.isPressed ? 0.25 : 0.1)))
            .overlay(forma.stroke(destacado ? Color.accentColor : Color.secondary.opacity(0.3),
                                  lineWidth: destacado ? 2 : 1))
            .contentShape(forma)
    }
}

struct PainelView: View {
    @ObservedObject var m: Manager
    let modo: Modo

    var body: some View {
        VStack(spacing: 14) {
            Text("Movimentos · Arminda Melo RL").font(.headline)
            HStack {
                Label(modo == .local ? "Servidor local" : "Servidor remoto",
                      systemImage: modo == .local ? "desktopcomputer" : "network")
                Spacer()
                Button("Mudar…") { m.mudarModo() }.disabled(m.ocupado)
            }
            if modo == .remoto {
                TextField("Servidor (utilizador@host)", text: $m.destino)
                    .textFieldStyle(.roundedBorder)
                TextField("Pasta do repo no servidor", text: $m.repoDir)
                    .textFieldStyle(.roundedBorder)
            } else {
                TextField("Pasta do repo neste Mac", text: $m.repoLocal)
                    .textFieldStyle(.roundedBorder)
            }
            HStack(spacing: 12) {
                Button("Arrancar servidor") { m.arrancarServidor() }
                if modo == .remoto {
                    Button("Ligar") { m.ligar() }
                    Button("Desligar") { m.parar() }
                } else {
                    Button("Abrir no browser") { m.ligar() }
                }
            }
            .disabled(m.ocupado)
            Text(m.status).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
    }
}
